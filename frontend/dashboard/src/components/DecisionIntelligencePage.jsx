import { useState, useEffect, useCallback } from 'react';
import { useTheme } from '../context/ThemeContext';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8080';

const PRIORITY_COLORS = {
  P1: { bg: 'bg-red-500/20', border: 'border-red-500/50', text: 'text-red-400', dot: 'bg-red-500' },
  P2: { bg: 'bg-orange-500/20', border: 'border-orange-500/50', text: 'text-orange-400', dot: 'bg-orange-500' },
  P3: { bg: 'bg-yellow-500/20', border: 'border-yellow-500/50', text: 'text-yellow-400', dot: 'bg-yellow-500' },
};

const HEALTH_COLORS = {
  Critical: 'text-red-400',
  Poor: 'text-orange-400',
  Fair: 'text-yellow-400',
  Good: 'text-green-400',
  Excellent: 'text-emerald-400',
};

export default function DecisionIntelligencePage() {
  const { theme } = useTheme();
  const dark = theme === 'dark';
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchDI = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/decision-intelligence`);
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const json = await res.json();
      setData(json);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDI(); }, [fetchDI]);

  const di = data?.decision_intelligence || {};
  const analytics = data?.analytics || {};

  const card = `rounded-2xl border p-5 ${
    dark ? 'bg-slate-800/60 border-slate-700/50' : 'bg-white border-gray-200'
  }`;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className={`text-2xl font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>
            🧠 Decision Intelligence
          </h1>
          <p className={`text-sm mt-0.5 ${dark ? 'text-slate-400' : 'text-gray-500'}`}>
            AI-powered analysis &amp; recommendations by Google Gemini
            {lastUpdated && <span className="ml-2 opacity-60">· Updated {lastUpdated}</span>}
          </p>
        </div>
        <button
          id="refresh-di-btn"
          onClick={fetchDI}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium
                     bg-blue-600 hover:bg-blue-700 text-white transition disabled:opacity-50"
        >
          <span className={loading ? 'animate-spin' : ''}>⟳</span>
          {loading ? 'Analyzing…' : 'Refresh Analysis'}
        </button>
      </div>

      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">
          ⚠️ {error} — <button onClick={fetchDI} className="underline">Retry</button>
        </div>
      )}

      {loading && !data && (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="w-12 h-12 rounded-full border-4 border-blue-500/30 border-t-blue-500 animate-spin" />
          <p className={`text-sm ${dark ? 'text-slate-400' : 'text-gray-500'}`}>
            Gemini AI is analyzing community data…
          </p>
        </div>
      )}

      {data && (
        <>
          {/* Community Health Score */}
          <div className={`${card} flex flex-col sm:flex-row sm:items-center gap-5`}>
            <div className="flex-shrink-0 flex items-center justify-center w-24 h-24 rounded-2xl
                            bg-gradient-to-br from-blue-600 to-violet-600 shadow-lg shadow-blue-500/25">
              <div className="text-center">
                <div className="text-3xl font-black text-white">
                  {di.overall_health_score ?? analytics.resolution_rate ?? 0}
                </div>
                <div className="text-[10px] text-blue-200 font-medium uppercase tracking-wider">Score</div>
              </div>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xl font-bold ${HEALTH_COLORS[di.health_status] || 'text-gray-400'}`}>
                  {di.health_status || 'Analyzing…'}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  dark ? 'bg-slate-700 text-slate-300' : 'bg-gray-100 text-gray-600'
                }`}>Community Health</span>
              </div>
              <p className={`text-sm leading-relaxed ${dark ? 'text-slate-300' : 'text-gray-600'}`}>
                {di.executive_summary || 'Loading executive summary…'}
              </p>
            </div>
            {/* Quick KPIs */}
            <div className="flex sm:flex-col gap-4 sm:gap-2 flex-shrink-0">
              {[
                { label: 'Total', value: analytics.total_complaints || 0, color: 'text-blue-400' },
                { label: 'Open', value: analytics.open || 0, color: 'text-orange-400' },
                { label: 'Critical', value: analytics.open_critical || 0, color: 'text-red-400' },
              ].map(kpi => (
                <div key={kpi.label} className="text-center">
                  <div className={`text-xl font-bold ${kpi.color}`}>{kpi.value}</div>
                  <div className={`text-xs ${dark ? 'text-slate-500' : 'text-gray-400'}`}>{kpi.label}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Critical Alerts */}
            <div className={card}>
              <h2 className={`text-base font-semibold mb-4 flex items-center gap-2 ${dark ? 'text-white' : 'text-gray-900'}`}>
                <span className="text-xl">🚨</span> Critical Alerts
              </h2>
              <div className="space-y-3">
                {(di.critical_alerts || []).length > 0 ? (
                  (di.critical_alerts || []).map((alert, i) => (
                    <div key={i}
                         className={`flex items-start gap-3 p-3 rounded-xl border
                                    ${dark ? 'bg-red-500/10 border-red-500/20' : 'bg-red-50 border-red-200'}`}>
                      <span className="text-red-400 mt-0.5 flex-shrink-0">⚡</span>
                      <p className={`text-sm ${dark ? 'text-red-300' : 'text-red-700'}`}>{alert}</p>
                    </div>
                  ))
                ) : (
                  <div className={`text-sm text-center py-8 ${dark ? 'text-slate-500' : 'text-gray-400'}`}>
                    ✅ No critical alerts
                  </div>
                )}
              </div>
            </div>

            {/* Decision Insights */}
            <div className={card}>
              <h2 className={`text-base font-semibold mb-4 flex items-center gap-2 ${dark ? 'text-white' : 'text-gray-900'}`}>
                <span className="text-xl">💡</span> AI Insights
              </h2>
              <div className="space-y-3">
                {(di.decision_insights || []).map((insight, i) => (
                  <div key={i}
                       className={`flex items-start gap-3 p-3 rounded-xl border
                                  ${dark ? 'bg-blue-500/10 border-blue-500/20' : 'bg-blue-50 border-blue-200'}`}>
                    <span className="text-blue-400 mt-0.5 flex-shrink-0 text-base">✦</span>
                    <p className={`text-sm ${dark ? 'text-blue-200' : 'text-blue-800'}`}>{insight}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Recommended Actions */}
          <div className={card}>
            <h2 className={`text-base font-semibold mb-4 flex items-center gap-2 ${dark ? 'text-white' : 'text-gray-900'}`}>
              <span className="text-xl">⚡</span> Recommended Actions
              <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${
                dark ? 'bg-slate-700 text-slate-400' : 'bg-gray-100 text-gray-500'
              }`}>Gemini AI Generated</span>
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {(di.recommendations || []).map((rec, i) => {
                const colors = PRIORITY_COLORS[rec.priority] || PRIORITY_COLORS.P3;
                return (
                  <div key={i}
                       className={`relative p-4 rounded-xl border ${colors.bg} ${colors.border} group
                                  hover:scale-[1.02] transition-transform`}>
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`w-2 h-2 rounded-full ${colors.dot}`} />
                      <span className={`text-xs font-bold ${colors.text}`}>{rec.priority}</span>
                      <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${
                        dark ? 'bg-slate-700/60 text-slate-400' : 'bg-white/80 text-gray-500'
                      }`}>{rec.timeline}</span>
                    </div>
                    <p className={`text-sm font-medium mb-2 ${dark ? 'text-white' : 'text-gray-900'}`}>
                      {rec.action}
                    </p>
                    <p className={`text-xs ${dark ? 'text-slate-400' : 'text-gray-500'}`}>
                      <strong>Impact:</strong> {rec.impact}
                    </p>
                    <p className={`text-xs mt-1 ${dark ? 'text-slate-500' : 'text-gray-400'}`}>
                      Category: {rec.category}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Risk by Category */}
          {analytics.risk_by_category && Object.keys(analytics.risk_by_category).length > 0 && (
            <div className={card}>
              <h2 className={`text-base font-semibold mb-4 flex items-center gap-2 ${dark ? 'text-white' : 'text-gray-900'}`}>
                <span className="text-xl">⚠️</span> Risk Scores by Category
              </h2>
              <div className="space-y-3">
                {Object.entries(analytics.risk_by_category)
                  .sort((a, b) => b[1] - a[1])
                  .map(([cat, score]) => {
                    const pct = Math.min(100, score);
                    const color = pct >= 75 ? 'bg-red-500' : pct >= 50 ? 'bg-orange-500' : pct >= 25 ? 'bg-yellow-500' : 'bg-green-500';
                    const label = pct >= 75 ? 'Critical' : pct >= 50 ? 'High' : pct >= 25 ? 'Moderate' : 'Low';
                    return (
                      <div key={cat} className="flex items-center gap-3">
                        <div className={`text-xs w-36 flex-shrink-0 ${dark ? 'text-slate-300' : 'text-gray-700'}`}>
                          {cat.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        </div>
                        <div className={`flex-1 h-2 rounded-full ${dark ? 'bg-slate-700' : 'bg-gray-200'}`}>
                          <div
                            className={`h-2 rounded-full ${color} transition-all duration-700`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <div className="flex items-center gap-2 w-24 flex-shrink-0">
                          <span className={`text-sm font-bold ${dark ? 'text-white' : 'text-gray-800'}`}>{pct}</span>
                          <span className={`text-xs ${dark ? 'text-slate-500' : 'text-gray-400'}`}>{label}</span>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* Gemini Attribution */}
          <div className={`flex items-center justify-center gap-3 py-3 rounded-xl border ${
            dark ? 'border-slate-700/50 text-slate-500' : 'border-gray-200 text-gray-400'
          } text-xs`}>
            <span>Powered by</span>
            <span className="font-semibold text-blue-500">Google Gemini 2.5 Flash</span>
            <span>·</span>
            <span>Analysis generated at {data.generated_at?.slice(0, 16).replace('T', ' ')} UTC</span>
          </div>
        </>
      )}
    </div>
  );
}
