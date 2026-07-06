import { useState, useEffect, useCallback } from 'react';
import { useTheme } from '../context/ThemeContext';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8080';

const CAT_COLORS = [
  '#3b82f6','#ef4444','#10b981','#f59e0b','#8b5cf6',
  '#ec4899','#06b6d4','#84cc16','#f97316','#6366f1','#14b8a6','#a855f7',
];
const SEV_COLORS = {
  critical: '#ef4444', high: '#f97316', moderate: '#f59e0b', low: '#10b981',
};

export default function AnalyticsPage() {
  const { theme } = useTheme();
  const dark = theme === 'dark';
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);

  const fetchAnalytics = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API}/analytics`);
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      setAnalytics(await res.json());
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

  const card = `rounded-2xl border p-5 ${
    dark ? 'bg-slate-800/60 border-slate-700/50' : 'bg-white border-gray-200'
  }`;
  const axisColor    = dark ? '#64748b' : '#9ca3af';
  const gridColor    = dark ? '#1e293b' : '#f3f4f6';
  const tooltipStyle = { backgroundColor: dark ? '#1e293b' : '#fff', border: '1px solid #374151', borderRadius: 8, fontSize: 12 };

  if (loading && !analytics) return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <div className="w-12 h-12 rounded-full border-4 border-blue-500/30 border-t-blue-500 animate-spin" />
      <p className={`text-sm ${dark ? 'text-slate-400' : 'text-gray-500'}`}>Loading analytics…</p>
    </div>
  );
  if (error) return (
    <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">
      ⚠️ {error} — <button onClick={fetchAnalytics} className="underline">Retry</button>
    </div>
  );
  if (!analytics) return null;

  const catData = Object.entries(analytics.category_distribution || {})
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({
      name: name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      value,
    }));

  const sevData = Object.entries(analytics.severity_distribution || {}).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
    fill: SEV_COLORS[name] || '#6366f1',
  }));

  const trendData = (analytics.monthly_trend || []).map(t => ({
    month: t.month,
    Complaints: t.count,
  }));

  const accel = analytics.acceleration || {};

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className={`text-2xl font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>
            📊 Analytics Dashboard
          </h1>
          <p className={`text-sm mt-0.5 ${dark ? 'text-slate-400' : 'text-gray-500'}`}>
            Community complaint data analysis &amp; insights
            {accel.rapids_enabled && (
              <span className="ml-2 text-xs text-emerald-400 font-medium">⚡ NVIDIA RAPIDS Accelerated</span>
            )}
          </p>
        </div>
        <button id="refresh-analytics-btn" onClick={fetchAnalytics}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-indigo-600 hover:bg-indigo-700 text-white transition">
          ⟳ Refresh
        </button>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {[
          { label: 'Total Complaints', value: analytics.total_complaints, icon: '📋', color: 'text-blue-400' },
          { label: 'Resolved',         value: analytics.resolved,         icon: '✅', color: 'text-green-400' },
          { label: 'Open',             value: analytics.open,             icon: '🔓', color: 'text-orange-400' },
          { label: 'Critical/High',    value: analytics.open_critical,    icon: '🚨', color: 'text-red-400' },
          { label: 'Resolution Rate',  value: `${analytics.resolution_rate}%`, icon: '📈', color: 'text-purple-400' },
        ].map(kpi => (
          <div key={kpi.label} className={`${card} text-center`}>
            <div className="text-2xl mb-1">{kpi.icon}</div>
            <div className={`text-2xl font-bold ${kpi.color}`}>{kpi.value ?? 0}</div>
            <div className={`text-xs mt-0.5 ${dark ? 'text-slate-500' : 'text-gray-400'}`}>{kpi.label}</div>
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Category Pie */}
        <div className={card}>
          <h2 className={`text-sm font-semibold mb-4 ${dark ? 'text-white' : 'text-gray-900'}`}>
            📂 Issue Category Distribution
          </h2>
          {catData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={catData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                     outerRadius={90} innerRadius={50} paddingAngle={2} label={({ name, percent }) =>
                       percent > 0.05 ? `${(percent * 100).toFixed(0)}%` : ''}>
                  {catData.map((_, i) => (
                    <Cell key={i} fill={CAT_COLORS[i % CAT_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} formatter={(val, name) => [val, name]} />
                <Legend wrapperStyle={{ fontSize: 11, color: axisColor }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className={`text-center py-10 text-sm ${dark ? 'text-slate-500' : 'text-gray-400'}`}>No data yet</div>
          )}
        </div>

        {/* Severity Bar */}
        <div className={card}>
          <h2 className={`text-sm font-semibold mb-4 ${dark ? 'text-white' : 'text-gray-900'}`}>
            ⚠️ Severity Distribution
          </h2>
          {sevData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={sevData} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                <XAxis dataKey="name" tick={{ fill: axisColor, fontSize: 11 }} />
                <YAxis tick={{ fill: axisColor, fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                  {sevData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className={`text-center py-10 text-sm ${dark ? 'text-slate-500' : 'text-gray-400'}`}>No data yet</div>
          )}
        </div>
      </div>

      {/* Monthly Trend */}
      <div className={card}>
        <h2 className={`text-sm font-semibold mb-4 ${dark ? 'text-white' : 'text-gray-900'}`}>
          📅 Monthly Complaint Trend
        </h2>
        {trendData.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={trendData} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis dataKey="month" tick={{ fill: axisColor, fontSize: 10 }} />
              <YAxis tick={{ fill: axisColor, fontSize: 11 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="Complaints" fill="#6366f1" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className={`text-center py-10 text-sm ${dark ? 'text-slate-500' : 'text-gray-400'}`}>
            Not enough historical data yet
          </div>
        )}
      </div>

      {/* Top Locations */}
      <div className={card}>
        <h2 className={`text-sm font-semibold mb-4 ${dark ? 'text-white' : 'text-gray-900'}`}>
          📍 Top Affected Locations
        </h2>
        <div className="space-y-3">
          {(analytics.top_locations || []).slice(0, 8).map((loc, i) => {
            const maxCount = analytics.top_locations[0]?.count || 1;
            const pct = Math.round((loc.count / maxCount) * 100);
            return (
              <div key={i} className="flex items-center gap-3">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                  i === 0 ? 'bg-yellow-500 text-white' : i === 1 ? 'bg-gray-400 text-white' :
                  i === 2 ? 'bg-amber-700 text-white' : dark ? 'bg-slate-700 text-slate-300' : 'bg-gray-100 text-gray-600'
                }`}>{i + 1}</div>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium truncate ${dark ? 'text-slate-200' : 'text-gray-800'}`}>{loc.location}</p>
                  <div className={`h-1.5 rounded-full mt-1 ${dark ? 'bg-slate-700' : 'bg-gray-200'}`}>
                    <div className="h-1.5 rounded-full bg-blue-500 transition-all duration-700" style={{ width: `${pct}%` }} />
                  </div>
                </div>
                <div className={`text-sm font-bold w-8 text-right ${dark ? 'text-white' : 'text-gray-900'}`}>{loc.count}</div>
              </div>
            );
          })}
          {!(analytics.top_locations || []).length && (
            <p className={`text-sm text-center py-8 ${dark ? 'text-slate-500' : 'text-gray-400'}`}>No location data yet</p>
          )}
        </div>
      </div>

      {/* Category Ranking Table */}
      <div className={card}>
        <h2 className={`text-sm font-semibold mb-4 ${dark ? 'text-white' : 'text-gray-900'}`}>🏆 Priority Ranking by Category</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={`${dark ? 'text-slate-400 border-b border-slate-700' : 'text-gray-500 border-b border-gray-200'}`}>
                <th className="text-left pb-3 font-medium">Rank</th>
                <th className="text-left pb-3 font-medium">Category</th>
                <th className="text-center pb-3 font-medium">Count</th>
                <th className="text-center pb-3 font-medium">Share</th>
                <th className="text-center pb-3 font-medium">Risk Score</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(analytics.category_distribution || {}).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([cat, count], i) => {
                const total = analytics.total_complaints || 1;
                const share = ((count / total) * 100).toFixed(1);
                const riskScore = analytics.risk_by_category?.[cat] || 0;
                return (
                  <tr key={cat} className={`${dark ? 'hover:bg-slate-700/30 border-b border-slate-700/30' : 'hover:bg-gray-50 border-b border-gray-100'} transition`}>
                    <td className={`py-3 ${dark ? 'text-slate-400' : 'text-gray-500'}`}>#{i + 1}</td>
                    <td className={`py-3 font-medium ${dark ? 'text-slate-200' : 'text-gray-800'}`}>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: CAT_COLORS[i % CAT_COLORS.length] }} />
                        {cat.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </div>
                    </td>
                    <td className={`py-3 text-center font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>{count}</td>
                    <td className={`py-3 text-center ${dark ? 'text-slate-400' : 'text-gray-500'}`}>{share}%</td>
                    <td className="py-3 text-center">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        riskScore >= 75 ? 'bg-red-500/20 text-red-400' :
                        riskScore >= 50 ? 'bg-orange-500/20 text-orange-400' :
                        riskScore >= 25 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-green-500/20 text-green-400'
                      }`}>{riskScore}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Acceleration Badge */}
      <div className={`flex items-center justify-center gap-3 py-3 rounded-xl border text-xs ${
        dark ? 'border-slate-700/50 text-slate-500' : 'border-gray-200 text-gray-400'
      }`}>
        <span>Data pipeline:</span>
        <span className={`font-semibold ${accel.rapids_enabled ? 'text-green-500' : 'text-blue-400'}`}>
          {accel.pandas_backend || 'pandas'}
        </span>
        <span>·</span>
        <span>{accel.note || 'CPU mode'}</span>
      </div>
    </div>
  );
}
