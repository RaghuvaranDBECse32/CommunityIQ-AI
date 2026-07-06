from dotenv import load_dotenv
load_dotenv()  # ADK reads GOOGLE_API_KEY from os.environ

from fastapi import FastAPI, UploadFile, Form, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from agents.orchestrator import orchestrator
from core.sse_queue import sse_queue
from core.database import get_db, ComplaintDB
from sqlalchemy.orm import Session
from fastapi import Depends
from fastapi.responses import JSONResponse
from core.redis_client import (redis_client, log_status_change,
                               get_status_history, get_cached_official_email,
                               cache_official_email)
import json, base64, os, logging
from typing import Optional
from datetime import datetime

# Direct tool imports for fallback pipeline (when Gemini is rate-limited)
from tools.gemini_tools import gemini_analyze_image
from tools.maps_tools import geocode_address, reverse_geocode
from tools.directory_tools import search_municipal_directory
from tools.db_tools import save_complaint
from tools.sse_tools import sse_push_map_update
from tools.gmail_tools import gmail_send_work_order
from tools.gemini_tools import gemini_lookup_official_email
from tools.exif_tools import extract_gps_from_image

logger = logging.getLogger(__name__)

# ── Configure root logging so ALL pipeline logs appear in terminal ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet down noisy libraries
for _quiet in ("httpcore", "httpx", "urllib3", "google.auth", "google.adk"):
    logging.getLogger(_quiet).setLevel(logging.WARNING)

app = FastAPI(title="CiviqAI Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])
print(">>> CiviqAI LOADED — deterministic pipeline active <<<", flush=True)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

session_service = InMemorySessionService()
runner = Runner(agent=orchestrator, app_name="civiqai",
                session_service=session_service)


# ── Health check ──────────────────────────────────────────────────
@app.get("/health")
def health_check():
    """Liveness probe for Docker / k8s."""
    return {"status": "healthy", "service": "civiqai"}


# ── Reverse geocode endpoint (for GPS button) ────────────────────
@app.get("/reverse-geocode")
def reverse_geocode_endpoint(
    lat: float = Query(...), lng: float = Query(...)
):
    """Convert GPS coordinates to address + municipality.
    Called by the frontend GPS 'Use my location' button."""
    logger.info("=" * 60)
    logger.info("REVERSE GEOCODE REQUEST: lat=%s  lng=%s", lat, lng)
    try:
        rev = reverse_geocode(lat, lng)
        logger.info("  Result: municipality=%s  area=%s  formatted=%s",
                    rev.get("municipality"), rev.get("area"),
                    rev.get("formatted_address", "")[:80])
        logger.info("=" * 60)
        return rev
    except Exception as e:
        logger.error("  Reverse geocode failed: %s", e)
        logger.info("=" * 60)
        return {"error": str(e), "ward": "Unknown", "municipality": "unknown"}


# ── Status update endpoint ────────────────────────────────────────
@app.patch("/complaints/{complaint_id}/status")
def update_status(complaint_id: str, request_body: dict = {},
                  db: Session = Depends(get_db)):
    """
    Update a complaint's status.  Accepts JSON body:
      { "status": "open"|"in_progress"|"resolved"|"closed",
        "changed_by": "officer" (optional) }

    Flow:
      1. Validate → 2. Update DB → 3. Log to Redis → 4. SSE broadcast
    """
    new_status = request_body.get("status")
    changed_by = request_body.get("changed_by", "officer")

    VALID = {"open", "in_progress", "resolved", "closed"}
    if not new_status or new_status not in VALID:
        return JSONResponse(status_code=400, content={
            "error": f"Invalid status. Must be one of: {', '.join(sorted(VALID))}"
        })

    complaint = db.query(ComplaintDB).filter(
        ComplaintDB.id == complaint_id
    ).first()
    if not complaint:
        return JSONResponse(status_code=404, content={
            "error": f"Complaint {complaint_id} not found"
        })

    old_status = complaint.status or "open"
    if old_status == new_status:
        return {"complaint_id": complaint_id, "status": new_status,
                "message": "No change"}

    # Update DB
    complaint.status = new_status  # type: ignore[assignment]
    if new_status == "resolved":
        complaint.resolved_at = datetime.utcnow()  # type: ignore[assignment]
    db.commit()

    # Log to Redis
    log_entry = log_status_change(
        complaint_id, old_status, new_status, changed_by
    )

    # SSE broadcast to all connected clients
    try:
        sse_push_map_update(
            event_type="status_update",
            complaint_id=str(complaint_id),
            lat=complaint.lat,
            lng=complaint.lng,
            status=new_status,
            issue_type=complaint.issue_type
        )
    except Exception:
        logger.warning("SSE push skipped for status update")

    logger.info("STATUS UPDATE: %s  %s → %s (by %s)",
                complaint_id, old_status, new_status, changed_by)
    return {
        "complaint_id": complaint_id,
        "old_status": old_status,
        "new_status": new_status,
        "changed_by": changed_by,
        "timestamp": log_entry["timestamp"]
    }


# ── Status history endpoint ───────────────────────────────────────
@app.get("/complaints/{complaint_id}/history")
def get_complaint_history(complaint_id: str):
    """Get full status change log for a complaint from Redis."""
    history = get_status_history(complaint_id)
    return {"complaint_id": complaint_id, "history": history}


# ── Citizen submits complaint with photo ──────────────────────────
@app.post("/complaint")
async def submit_complaint(
    image: UploadFile,
    location: str = Form(default=None),
    citizen_email: str = Form(default=None),
    lat: Optional[float] = Form(default=None),
    lng: Optional[float] = Form(default=None),
):
    logger.info("=" * 60)
    logger.info("NEW COMPLAINT SUBMISSION")
    logger.info("Location: %s | Citizen: %s | Image: %s",
                location or "(from EXIF)", citizen_email or "anonymous", image.filename)
    if lat and lng:
        logger.info("GPS coordinates provided: lat=%s  lng=%s", lat, lng)
    
    image_bytes = await image.read()
    img_path = f"uploads/{image.filename}"
    with open(img_path, "wb") as f:
        f.write(image_bytes)
    logger.info("Image saved to: %s", img_path)

    # ── Extract GPS from image EXIF metadata if not provided ──────
    if not (lat and lng):
        logger.info("No GPS from form — trying EXIF metadata...")
        exif_gps = extract_gps_from_image(img_path)
        if exif_gps:
            lat = exif_gps["lat"]
            lng = exif_gps["lng"]
            logger.info("  ✓ EXIF GPS: lat=%s  lng=%s", lat, lng)
        else:
            logger.info("  No EXIF GPS found in image")

    # If still no location text, derive from coordinates
    if not location and lat and lng:
        try:
            rev = reverse_geocode(lat, lng)
            location = rev.get("formatted_address") or rev.get("area") or f"{lat}, {lng}"
            logger.info("  Location from EXIF reverse-geocode: %s", location)
        except Exception:
            location = f"{lat}, {lng}"
    elif not location:
        location = "Unknown location"

    # Always use deterministic 7-step pipeline for complaint submissions.
    # The ADK orchestrator is unreliable here — the LLM often stops after
    # just 1 agent step.  ADK is still used for /chat where reasoning matters.
    return await _complaint_pipeline(img_path, location, citizen_email,
                                     gps_lat=lat, gps_lng=lng)


# ── Deterministic complaint pipeline ──────────────────────────────
async def _complaint_pipeline(img_path: str, location: str,
                               citizen_email: str | None,
                               gps_lat: Optional[float] = None,
                               gps_lng: Optional[float] = None):
    """
    Process a civic complaint through 7 deterministic steps.
    Calls tools directly for reliability (no LLM orchestration drift).

    FLOW:
      1. Image analysis  (Gemini Vision — gracefully degrades)
      2. Geocode         (Nominatim / OSM — use GPS coords if provided)
      3. Reverse geocode (get ward/zone/municipality)
      4. Directory lookup (find responsible officer + email from Redis)
      5. Save to DB      (SQLite)
      6. Email dispatch  (send work order to municipality)
      7. SSE push        (notify dashboard)
    """
    logger.info("-" * 60)
    logger.info("COMPLAINT PIPELINE START")
    logger.info("  img_path=%s  location=%s  gps=(%s, %s)",
                img_path, location, gps_lat, gps_lng)

    # ── Step 1 — Image analysis (try Gemini, gracefully degrade) ──
    logger.info("Step 1/7: Image analysis (may degrade)...")
    analysis = gemini_analyze_image(img_path, location)
    issue_type  = analysis.get("issue_type", "other")
    severity    = analysis.get("severity", "moderate")
    description = analysis.get("description", "Civic issue reported by citizen")
    logger.info("  Result: issue=%s  severity=%s  desc=%s",
                issue_type, severity, description[:80])

    # ── Step 2 — Geocode location (Google Maps, NOT Gemini) ───────
    logger.info("Step 2/7: Geocoding...")
    lat, lng, formatted = gps_lat, gps_lng, location
    if lat and lng:
        logger.info("  Using GPS coordinates directly: (%s, %s)", lat, lng)
    else:
        try:
            geo = geocode_address(location)
            lat = geo.get("lat")
            lng = geo.get("lng")
            formatted = geo.get("formatted", location)
            logger.info("  Geocoded '%s' → (%s, %s)", location, lat, lng)
        except Exception as ge:
            logger.warning("  Geocoding failed: %s", ge)

    # ── Step 3 — Reverse geocode for ward/zone/municipality ───────
    ward, zone, municipality = "Unknown", "Unknown", "unknown"
    rev_data = {}
    if lat and lng:
        logger.info("Step 3/7: Reverse geocoding (%s, %s)...", lat, lng)
        try:
            rev_data = reverse_geocode(lat, lng)
            ward         = rev_data.get("ward", "Unknown")
            zone         = rev_data.get("zone", "Unknown")
            municipality = rev_data.get("municipality", "unknown")
            if rev_data.get("formatted_address"):
                formatted = rev_data["formatted_address"]
            logger.info("  → Ward=%s  Zone=%s  Municipality=%s",
                        ward, zone, municipality)
        except Exception as re_:
            logger.warning("  Reverse geocode failed: %s", re_)
    else:
        logger.info("Step 3/7: Skipped (no coordinates)")

    # ── Step 4 — Municipal directory lookup (Redis) ───────────────
    logger.info("Step 4/7: Looking up responsible officer for '%s' / '%s'...",
                municipality, issue_type)
    officer = {}
    try:
        officer = search_municipal_directory(
            ward=ward, issue_type=issue_type, municipality=municipality
        )
    except Exception as de:
        logger.warning("  Directory lookup failed: %s", de)
        officer = {
            "officer_name": "Duty Officer",
            "email": "complaints@chennaicorporation.gov.in",
            "department": "Greater Chennai Corporation",
            "municipality": "Greater Chennai Corporation",
        }
    muni_email = officer.get("email", "complaints@chennaicorporation.gov.in")
    muni_name  = officer.get("municipality", officer.get("department", "Unknown"))
    logger.info("  → Officer: %s  Email: %s  Municipality: %s",
                officer.get("officer_name"), muni_email, muni_name)

    # ── Step 5 — Save complaint to database (SQLite) ──────────────
    logger.info("Step 5/7: Saving complaint to database...")
    result = save_complaint(
        issue_type=issue_type,
        description=description,
        location_text=formatted,
        lat=lat, lng=lng,
        ward=ward, zone=zone,
        severity=severity,
        citizen_email=citizen_email,
        image_url=f"uploads/{os.path.basename(img_path)}"
    )
    cid = result.get("complaint_id", "unknown")
    logger.info("  → Saved as complaint #%s", cid)

    # ── Step 6 — Email dispatch (send work order to municipality) ─
    logger.info("Step 6/7: Sending work order email to %s (%s)...",
                muni_name, muni_email)

    # -- Fetch official corporation email via Google Search ----------
    official_email = None
    muni_key = officer.get("ward", municipality or "")
    if muni_key:
        official_email = get_cached_official_email(muni_key)
        if official_email:
            logger.info("  → Official email (cached): %s", official_email)
        else:
            logger.info("  → Searching Google for official email of '%s'...", muni_name)
            official_email = gemini_lookup_official_email(muni_name)
            if official_email:
                cache_official_email(muni_key, official_email)
    if not official_email:
        logger.info("  → No official email found; sending to officer only")

    # Build the org-mail row for the email body
    org_email_row = ""
    if official_email:
        org_email_row = (
            f'<tr><td style="padding:6px 0;color:#6b7280">Org Mail</td>'
            f'<td style="padding:6px 0;font-weight:600">'
            f'<a href="mailto:{official_email}" style="color:#2563eb">'
            f'{official_email}</a></td></tr>'
        )

    email_status = "skipped"
    try:
        subject = f"[CiviqAI] Work Order — {issue_type.replace('_', ' ').title()} — #{cid}"
        html_body = f"""
        <div style="font-family:sans-serif;max-width:600px;padding:20px;border:1px solid #e5e7eb;border-radius:12px">
          <h2 style="color:#1e40af;margin-bottom:4px">🏛️ CiviqAI Work Order</h2>
          <p style="color:#6b7280;font-size:13px;margin-top:0">Complaint #{cid}</p>
          <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0"/>
          <table style="width:100%;font-size:14px;border-collapse:collapse">
            <tr><td style="padding:6px 0;color:#6b7280;width:140px">Issue Type</td>
                <td style="padding:6px 0;font-weight:600">{issue_type.replace('_', ' ').title()}</td></tr>
            <tr><td style="padding:6px 0;color:#6b7280">Severity</td>
                <td style="padding:6px 0;font-weight:600;color:{'#ef4444' if severity == 'critical' else '#f59e0b' if severity == 'high' else '#3b82f6'}">{severity.upper()}</td></tr>
            <tr><td style="padding:6px 0;color:#6b7280">Location</td>
                <td style="padding:6px 0">{formatted}</td></tr>
            <tr><td style="padding:6px 0;color:#6b7280">Coordinates</td>
                <td style="padding:6px 0">{lat}, {lng}</td></tr>
            <tr><td style="padding:6px 0;color:#6b7280">Ward / Zone</td>
                <td style="padding:6px 0">{ward} / {zone}</td></tr>
            <tr><td style="padding:6px 0;color:#6b7280">Municipality</td>
                <td style="padding:6px 0;font-weight:600">{muni_name}</td></tr>
            {org_email_row}
            <tr><td style="padding:6px 0;color:#6b7280">Assigned To</td>
                <td style="padding:6px 0">{officer.get('officer_name', 'Duty Officer')}</td></tr>
          </table>
          <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0"/>
          <p style="font-size:14px;color:#374151"><strong>Description:</strong> {description}</p>
          {f'<p style="font-size:13px;color:#6b7280">📧 Citizen: {citizen_email}</p>' if citizen_email else ''}
          <p style="font-size:11px;color:#9ca3af;margin-top:20px">
            Generated by CiviqAI — Civic Intelligence Platform
          </p>
        </div>
        """
        send_result = gmail_send_work_order(
            to=muni_email,
            complaint_id=str(cid),
            subject=subject,
            html_body=html_body,
            image_path=img_path,
            cc=official_email
        )
        email_status = send_result.get("status", "unknown")
        logger.info("  → ✅ Email sent! Message ID: %s", send_result.get("message_id"))
        if official_email:
            logger.info("  → ✅ CC'd official corporation email: %s", official_email)
    except Exception as email_err:
        email_status = "failed"
        logger.error("  → ❌ Email dispatch failed: %s", email_err)

    # ── Step 7 — Push SSE update to dashboard ─────────────────────
    logger.info("Step 7/7: Pushing SSE update to dashboard...")
    try:
        sse_push_map_update(
            event_type="new_pin",
            complaint_id=cid,
            lat=lat, lng=lng,
            status="open",
            issue_type=issue_type
        )
        logger.info("  → SSE push sent")
    except Exception:
        logger.warning("  → SSE push skipped (no listeners)")

    # ── Summary ───────────────────────────────────────────────────
    email_line = (
        f"📧 Work order emailed to: {muni_email}\n"
        if email_status == "sent"
        else f"📧 Email dispatch: {email_status}\n"
    )

    org_line = (
        f"🏢 Org Mail: {official_email}\n" if official_email else ""
    )

    summary = (
        f"✅ Complaint #{cid} registered!\n\n"
        f"📍 Location: {formatted}\n"
        f"🔍 Issue: {issue_type} ({severity} severity)\n"
        f"📝 {description}\n"
        f"🏛️ Municipality: {muni_name}\n"
        f"👤 Assigned to: {officer.get('officer_name', 'Duty Officer')} "
        f"({officer.get('department', 'N/A')})\n"
        f"{email_line}"
        f"{org_line}\n"
        f"Track your complaint at the portal feed."
    )

    logger.info("-" * 60)
    logger.info("COMPLAINT PIPELINE COMPLETE")
    logger.info("  Complaint: #%s", cid)
    logger.info("  Municipality: %s", muni_name)
    logger.info("  Officer: %s", officer.get("officer_name"))
    logger.info("  Email to: %s → %s", muni_email, email_status)
    if official_email:
        logger.info("  Org Mail (CC): %s", official_email)
    logger.info("=" * 60)
    return {"status": "processing", "message": summary}


# ── Gmail Pub/Sub webhook ─────────────────────────────────────────
@app.post("/inbox")
async def inbox_webhook(request: Request):
    body = await request.json()
    pubsub_msg = body.get("message", {})
    data_b64   = pubsub_msg.get("data", "")

    try:
        payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
    except Exception:
        payload = {}

    history_id = payload.get("historyId", "")
    email_addr = payload.get("emailAddress", "")

    session = await session_service.create_session(
        app_name="civiqai",
        user_id="system",
        state={"app:history_id": history_id}
    )

    try:
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=Content(role="user", parts=[Part(text=(
                f"New email received in Gmail inbox.\n"
                f"history_id: {history_id}\n"
                f"from: {email_addr}\n"
                f"Fetch the latest message and process it."
            ))])
        ):
            if event.is_final_response():
                break
    except Exception as e:
        if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
            logger.warning("Gemini API rate limit hit on inbox: %s", e)
            return JSONResponse(status_code=429, content={
                "status": "rate_limited",
                "message": "AI service rate limited. Will retry."
            })
        raise

    return {"status": "ok"}


# ── Officer chat ──────────────────────────────────────────────────
@app.post("/chat")
async def officer_chat(request: Request):
    body = await request.json()
    officer_id  = body.get("officer_id", "officer_1")
    session_id  = body.get("session_id", "officer_session")
    message_text = body.get("message", "")
    normalized = str(message_text).strip().lower()

    if normalized in {"hi", "hello", "hey", "yo", "good morning", "good afternoon", "good evening"}:
        return {
            "reply": "Hi! I can help with complaint trends, clusters, and status. Try: 'show open P1 complaints'."
        }

    # Create session if it doesn't exist
    try:
        await session_service.create_session(
            app_name="civiqai",
            user_id=officer_id,
            session_id=session_id,
            state={}
        )
    except Exception:
        pass  # session already exists

    response_text = ""
    try:
        async for event in runner.run_async(
            user_id=officer_id,
            session_id=session_id,
            new_message=Content(
                role="user",
                parts=[Part(text=message_text)]
            )
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_text = part.text
                            break
    except Exception as e:
        err_str = str(e)
        if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
            logger.warning("Gemini API rate limit hit on chat")
            return JSONResponse(status_code=429, content={
                "reply": "⏳ AI service is temporarily rate-limited. Please wait ~60 seconds and try again."
            })
        if "NOT_FOUND" in err_str or "404" in err_str:
            logger.error("Gemini model not found: %s", err_str[:200])
            return JSONResponse(status_code=500, content={
                "reply": "⚠️ AI model configuration error. The admin has been notified."
            })
        logger.error("Chat pipeline error: %s", err_str[:300])
        return JSONResponse(status_code=500, content={
            "reply": "❌ Something went wrong processing your request. Please try again."
        })

    return {"reply": response_text}


# ── SSE stream for live map ───────────────────────────────────────
@app.get("/stream")
async def sse_stream():
    async def event_generator():
        async for chunk in sse_queue.listen():  # async for on async generator
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "Connection":        "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ── Public portal — fetch complaints ─────────────────────────────
@app.get("/complaints")
def get_complaints(
    status:     Optional[str] = None,
    issue_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(ComplaintDB)
    if status:     q = q.filter(ComplaintDB.status == status)
    if issue_type: q = q.filter(ComplaintDB.issue_type == issue_type)
    complaints = q.order_by(ComplaintDB.submitted_at.desc()).limit(100).all()
    return [{
        "id":           c.id,
        "issue_type":   c.issue_type,
        "description":  c.description,
        "location":     c.location_text,
        "location_text": c.location_text,
        "lat":          c.lat,
        "lng":          c.lng,
        "severity":     c.severity,
        "status":       c.status,
        "priority":     c.priority,
        "image_url":    c.image_url,
        "streetview_url": c.streetview_url,
        "prediction":   c.prediction,
        "department":     c.department,
        "officer_name":   c.officer_name,
        "work_order_id":  c.work_order_id,
        "submitted_at": str(c.submitted_at)
    } for c in complaints]


# ======================================================================
# DECISION INTELLIGENCE API ENDPOINTS
# ======================================================================

from analytics.pipeline import compute_analytics, compute_forecast, clean_complaints
from analytics.pdf_report import generate_pdf_report
from tools.gemini_tools import (
    gemini_decision_intelligence,
    gemini_forecast_analysis,
)
from fastapi.responses import Response
import csv, io as _io


def _get_all_complaints_as_dicts(db: Session) -> list:
    complaints = db.query(ComplaintDB).order_by(
        ComplaintDB.submitted_at.desc()
    ).limit(2000).all()
    return [{
        "id":            c.id,
        "issue_type":    c.issue_type or "other",
        "description":   c.description or "",
        "location_text": c.location_text or "Unknown",
        "lat":           c.lat,
        "lng":           c.lng,
        "severity":      c.severity or "moderate",
        "status":        c.status or "open",
        "priority":      c.priority or "P3",
        "department":    c.department or "",
        "submitted_at":  str(c.submitted_at),
    } for c in complaints]


@app.get("/analytics")
def get_analytics(db: Session = Depends(get_db)):
    """Full analytics data — runs RAPIDS/pandas cleaning pipeline."""
    raw = _get_all_complaints_as_dicts(db)
    cleaned = clean_complaints(raw)
    analytics = compute_analytics(cleaned)
    return analytics


@app.get("/complaints/stats")
def get_complaints_stats(db: Session = Depends(get_db)):
    """Quick stats summary for the header bar."""
    total    = db.query(ComplaintDB).count()
    open_c   = db.query(ComplaintDB).filter(ComplaintDB.status == "open").count()
    resolved = db.query(ComplaintDB).filter(ComplaintDB.status == "resolved").count()
    in_prog  = db.query(ComplaintDB).filter(ComplaintDB.status == "in_progress").count()
    critical = db.query(ComplaintDB).filter(
        ComplaintDB.status == "open",
        ComplaintDB.severity.in_(["critical", "high"])
    ).count()
    return {
        "total": total,
        "open": open_c,
        "resolved": resolved,
        "in_progress": in_prog,
        "open_critical": critical,
        "resolution_rate": round((resolved / total * 100), 1) if total > 0 else 0,
    }


@app.get("/decision-intelligence")
def get_decision_intelligence(db: Session = Depends(get_db)):
    """Core Decision Intelligence endpoint powered by Gemini AI."""
    logger.info("=== DECISION INTELLIGENCE REQUEST ===")
    raw = _get_all_complaints_as_dicts(db)
    cleaned = clean_complaints(raw)
    analytics = compute_analytics(cleaned)
    di_result = gemini_decision_intelligence(analytics)
    return {
        "analytics": analytics,
        "decision_intelligence": di_result,
        "generated_at": datetime.utcnow().isoformat(),
    }


@app.get("/forecast")
def get_forecast(months: int = 3, db: Session = Depends(get_db)):
    """Forecast future complaint volumes + Gemini risk analysis."""
    logger.info("=== FORECAST REQUEST (months=%d) ===", months)
    raw = _get_all_complaints_as_dicts(db)
    cleaned = clean_complaints(raw)
    analytics = compute_analytics(cleaned)
    forecast_data = compute_forecast(cleaned, months_ahead=months)
    gemini_fcast = gemini_forecast_analysis(analytics, forecast_data)
    return {
        "forecast": forecast_data,
        "gemini_analysis": gemini_fcast,
        "months_ahead": months,
        "generated_at": datetime.utcnow().isoformat(),
    }


@app.get("/complaints/download-pdf")
def download_pdf_report(db: Session = Depends(get_db)):
    """Generate and download a professional PDF Decision Intelligence report."""
    logger.info("=== PDF REPORT GENERATION ===")
    raw = _get_all_complaints_as_dicts(db)
    cleaned = clean_complaints(raw)
    analytics = compute_analytics(cleaned)
    try:
        di = gemini_decision_intelligence(analytics)
        executive_summary = di.get("executive_summary", "")
        recs = di.get("recommendations", [])
        rec_strings = [
            f"[{r.get('priority','?')}] {r.get('action','')} -- {r.get('timeline','')}"
            for r in recs
        ]
    except Exception:
        executive_summary = ""
        rec_strings = []

    pdf_bytes = generate_pdf_report(
        analytics=analytics,
        recommendations=rec_strings,
        executive_summary=executive_summary,
        date_range="All Time"
    )
    filename = f"communityiq_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/complaints/bulk-import")
async def bulk_import_complaints(
    file: UploadFile,
    db: Session = Depends(get_db)
):
    """Bulk import complaints from CSV file."""
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    reader = csv.DictReader(_io.StringIO(text))
    imported = 0
    errors = 0
    for row in reader:
        try:
            from tools.db_tools import save_complaint
            save_complaint(
                issue_type    = row.get("issue_type", "other"),
                description   = row.get("description", ""),
                location_text = row.get("location_text", row.get("location", "Unknown")),
                severity      = row.get("severity", "moderate"),
                citizen_email = row.get("citizen_email"),
            )
            imported += 1
        except Exception as e:
            errors += 1
            logger.warning("Bulk import row error: %s", e)
    logger.info("Bulk import: %d imported, %d errors", imported, errors)
    return {"imported": imported, "errors": errors, "status": "complete"}
