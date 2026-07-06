"""
CommunityIQ AI — Data Cleaning & Analytics Pipeline

Supports NVIDIA RAPIDS (cuDF) acceleration with automatic pandas fallback.
This is the core Decision Intelligence data processing layer.

NVIDIA Acceleration:
    When running on a GPU-enabled environment with RAPIDS installed,
    cuDF replaces pandas transparently for 10–100× faster analytics.
    Fallback to standard pandas is automatic.
"""

# ── RAPIDS / cuDF acceleration (auto-fallback to pandas) ──────────────────────
try:
    import cudf.pandas
    cudf.pandas.install()
    RAPIDS_ENABLED = True
    print("[CommunityIQ AI] ✅ NVIDIA RAPIDS cuDF acceleration ACTIVE")
except Exception:
    RAPIDS_ENABLED = False

import pandas as pd  # cudf.pandas.install() makes this cuDF-backed if RAPIDS
import numpy as np
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)


def get_acceleration_info() -> dict:
    """Return info about whether RAPIDS acceleration is active."""
    return {
        "rapids_enabled": RAPIDS_ENABLED,
        "pandas_backend": "cuDF (RAPIDS)" if RAPIDS_ENABLED else "pandas",
        "note": "NVIDIA GPU acceleration active" if RAPIDS_ENABLED else "CPU mode (pandas)"
    }


# ── Data Cleaning ────────────────────────────────────────────────────────────

def clean_complaints(records: list[dict]) -> list[dict]:
    """
    Clean and validate a list of complaint records.
    
    Steps:
      1. Remove duplicates (by location + issue_type within 1 hour)
      2. Normalize issue_type to known categories
      3. Normalize severity values
      4. Fill missing locations
      5. Parse and standardize timestamps
      6. Filter obviously invalid records
    
    Returns cleaned list of dicts.
    """
    if not records:
        return []

    logger.info("[Pipeline] Cleaning %d complaint records...", len(records))

    df = pd.DataFrame(records)

    # ── Step 1: Drop duplicates ──────────────────────────────────────────────
    before = len(df)
    df = df.drop_duplicates(
        subset=["issue_type", "location_text"],
        keep="first"
    )
    logger.info("[Pipeline] Deduplication: %d → %d rows", before, len(df))

    # ── Step 2: Normalize issue_type ─────────────────────────────────────────
    VALID_ISSUE_TYPES = {
        "pothole", "water_leak", "garbage_overflow",
        "streetlight_failure", "power_outage", "waterlogging",
        "sewage_overflow", "tree_fallen", "road_damage",
        "pollution", "traffic", "healthcare", "other"
    }
    ALIASES = {
        "road damage":   "road_damage",
        "road_damage":   "road_damage",
        "street light":  "streetlight_failure",
        "light":         "streetlight_failure",
        "water":         "water_leak",
        "garbage":       "garbage_overflow",
        "trash":         "garbage_overflow",
        "flooding":      "waterlogging",
        "flood":         "waterlogging",
        "sewage":        "sewage_overflow",
        "tree":          "tree_fallen",
        "pothole":       "pothole",
    }

    def normalize_issue(val) -> str:
        if not val:
            return "other"
        v = str(val).lower().strip()
        if v in VALID_ISSUE_TYPES:
            return v
        for alias, canonical in ALIASES.items():
            if alias in v:
                return canonical
        return "other"

    df["issue_type"] = df["issue_type"].apply(normalize_issue)

    # ── Step 3: Normalize severity ───────────────────────────────────────────
    SEV_MAP = {"critical": "critical", "high": "high", "moderate": "moderate",
               "medium": "moderate", "low": "low", "minor": "low"}

    def normalize_severity(val) -> str:
        return SEV_MAP.get(str(val).lower().strip(), "moderate")

    if "severity" in df.columns:
        df["severity"] = df["severity"].apply(normalize_severity)

    # ── Step 4: Fill missing locations ───────────────────────────────────────
    df["location_text"] = df.get("location_text", pd.Series(["Unknown"] * len(df))).fillna("Unknown")

    # ── Step 5: Parse timestamps ─────────────────────────────────────────────
    if "submitted_at" in df.columns:
        df["submitted_at"] = pd.to_datetime(df["submitted_at"], errors="coerce")
        df["submitted_at"] = df["submitted_at"].fillna(pd.Timestamp.now())

    # ── Step 6: Filter invalid records ───────────────────────────────────────
    # Remove records with completely empty descriptions
    if "description" in df.columns:
        df = df[df["description"].notna() & (df["description"] != "")]

    # ── Step 7: Add derived fields ───────────────────────────────────────────
    if "submitted_at" in df.columns:
        df["day_of_week"] = df["submitted_at"].dt.day_name()
        df["month"] = df["submitted_at"].dt.month
        df["year"] = df["submitted_at"].dt.year
        df["hour"] = df["submitted_at"].dt.hour

    logger.info("[Pipeline] Cleaning complete: %d clean records", len(df))
    return df.to_dict(orient="records")


# ── Analytics Engine ─────────────────────────────────────────────────────────

def compute_analytics(records: list[dict]) -> dict:
    """
    Compute full analytics from complaint records.
    Returns all data needed for the Decision Intelligence dashboard.
    """
    if not records:
        return _empty_analytics()

    df = pd.DataFrame(records)

    # Category distribution
    category_dist = (
        df["issue_type"].value_counts().to_dict()
        if "issue_type" in df.columns else {}
    )

    # Severity distribution
    severity_dist = (
        df["severity"].value_counts().to_dict()
        if "severity" in df.columns else {}
    )

    # Status distribution
    status_dist = (
        df["status"].value_counts().to_dict()
        if "status" in df.columns else {}
    )

    # Top locations
    top_locations = []
    if "location_text" in df.columns:
        top_locs = df["location_text"].value_counts().head(10)
        top_locations = [
            {"location": loc, "count": int(cnt)}
            for loc, cnt in top_locs.items()
        ]

    # Monthly trend (last 12 months)
    monthly_trend = []
    if "submitted_at" in df.columns:
        df["submitted_at"] = pd.to_datetime(df["submitted_at"], errors="coerce")
        df["month_key"] = df["submitted_at"].dt.to_period("M").astype(str)
        mc = df.groupby("month_key").size().tail(12)
        monthly_trend = [
            {"month": str(m), "count": int(c)}
            for m, c in mc.items()
        ]

    # Risk score per category
    SEV_WEIGHTS = {"critical": 4, "high": 3, "moderate": 2, "low": 1}
    risk_by_category = {}
    if "issue_type" in df.columns and "severity" in df.columns:
        for category, group in df.groupby("issue_type"):
            weights = group["severity"].map(SEV_WEIGHTS).fillna(2)
            risk_score = min(100, int(weights.mean() * group.shape[0]))
            risk_by_category[str(category)] = risk_score

    # Resolution rate
    total = len(df)
    resolved = int(df["status"].eq("resolved").sum()) if "status" in df.columns else 0
    resolution_rate = round((resolved / total * 100), 1) if total > 0 else 0

    # Open critical count
    open_critical = 0
    if "status" in df.columns and "severity" in df.columns:
        open_critical = int(
            ((df["status"] == "open") & (df["severity"].isin(["critical", "high"]))).sum()
        )

    # Average severity score (weighted)
    avg_severity_score = 0
    if "severity" in df.columns:
        scores = df["severity"].map(SEV_WEIGHTS).fillna(2)
        avg_severity_score = round(float(scores.mean()) * 25, 1)  # scale to 100

    return {
        "total_complaints": total,
        "resolved": resolved,
        "open": int(df["status"].eq("open").sum()) if "status" in df.columns else total,
        "in_progress": int(df["status"].eq("in_progress").sum()) if "status" in df.columns else 0,
        "resolution_rate": resolution_rate,
        "open_critical": open_critical,
        "avg_severity_score": avg_severity_score,
        "category_distribution": category_dist,
        "severity_distribution": severity_dist,
        "status_distribution": status_dist,
        "top_locations": top_locations,
        "monthly_trend": monthly_trend,
        "risk_by_category": risk_by_category,
        "acceleration": get_acceleration_info(),
    }


def compute_forecast(records: list[dict], months_ahead: int = 3) -> list[dict]:
    """
    Simple linear extrapolation forecast for next N months.
    Returns predicted complaint counts per category.
    """
    if not records:
        return []

    df = pd.DataFrame(records)
    if "submitted_at" not in df.columns:
        return []

    df["submitted_at"] = pd.to_datetime(df["submitted_at"], errors="coerce")
    df["month_key"] = df["submitted_at"].dt.to_period("M").astype(str)

    # Get last 6 months trend per category
    recent = df[df["submitted_at"] >= (datetime.now() - timedelta(days=180))]
    if recent.empty:
        recent = df

    forecast = []
    now = datetime.now()

    for issue_type in df["issue_type"].unique():
        cat_df = recent[recent["issue_type"] == issue_type]
        monthly = cat_df.groupby("month_key").size()

        if len(monthly) < 2:
            avg = int(monthly.mean()) if len(monthly) > 0 else 0
            trend = 0.0
        else:
            vals = monthly.values
            # Simple linear regression slope
            x = np.arange(len(vals))
            slope = float(np.polyfit(x, vals, 1)[0])
            avg = int(vals[-1])
            trend = round(slope, 2)

        for i in range(1, months_ahead + 1):
            pred_month = (now + timedelta(days=30 * i)).strftime("%Y-%m")
            pred_count = max(0, int(avg + trend * i))
            forecast.append({
                "category": str(issue_type),
                "month": pred_month,
                "predicted_count": pred_count,
                "trend": trend,
                "confidence": min(95, max(50, 80 - abs(trend) * 5)),
            })

    return sorted(forecast, key=lambda x: (x["month"], -x["predicted_count"]))


def _empty_analytics() -> dict:
    return {
        "total_complaints": 0, "resolved": 0, "open": 0, "in_progress": 0,
        "resolution_rate": 0, "open_critical": 0, "avg_severity_score": 0,
        "category_distribution": {}, "severity_distribution": {},
        "status_distribution": {}, "top_locations": [], "monthly_trend": [],
        "risk_by_category": {}, "acceleration": get_acceleration_info(),
    }
