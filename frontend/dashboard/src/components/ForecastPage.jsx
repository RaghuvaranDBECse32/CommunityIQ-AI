import { useState, useEffect, useCallback, useRef } from 'react';
import { useTheme } from '../context/ThemeContext';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement, PointElement,
  Title, Tooltip, Legend, Filler
);

const API = import.meta.env.VITE_API_URL || 'http://localhost:8080';

export default function ForecastPage() {
  const { theme } = useTheme();
  const dark = theme === 'dark';
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [months, setMonths] = useState(3);
  const [pdfLoading, setPdfLoading] = useState(false);

  const fetchForecast = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/forecast?months=${months}`);
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [months]);

  useEffect(() => { fetchForecast(); }, [fetchForecast]);

  const downloadPdf = async () => {
    setPdfLoading(true);
    try {
      const res = await fetch(`${API}/complaints/download-pdf`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `communityiq_report_${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('PDF generation failed: ' + e.message);
    } finally {
      setPdfLoading(false);
    }
  };

  const card = `rounded-2xl border p-5 ${
    dark ? 'bg-slate-800/60 border-slate-700/50' : 'bg-white border-gray-200'
  }`;

  // Build chart data from forecast
  const forecast = data?.forecast || [];
  const gemini = data?.gemini_analysis || {};

  // Group forecast by month (sum all categories)
  const monthMap = {};
  forecast.forEach(f => {
    monthMap[f.month] = (monthMap[f.month] || 0) + f.predicted_count;
  });
  const chartLabels = Object.keys(monthMap).sort();
  const chartValues = chartLabels.map(m => monthMap[m]);

  // Group by category
  const catMap = {};
  forecast.forEach(f => {
    if (!catMap[f.category]) catMap[f.category] = [];
    catMap[f.category].push(f.predicted_count);
  });

  const CHART_COLORS = [
    '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
    '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
  ];

  const barData = {
    labels: chartLabels,
    datasets: [{
      label: 'Predicted Complaints',
      data: chartValues,
      backgroundColor: 'rgba(59,130,246,0.7)',
      borderColor: '#3b82f6',
      borderWidth: 2,
      borderRadius: 8,
    }],
  };

  const lineData = {
    labels: chartLabels,
    datasets: Object.entries(catMap).slice(0, 5).map(([cat, vals], i) => ({
      label: cat.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      data: vals,
      borderColor: CHART_COLORS[i % CHART_COLORS.length],
      backgroundColor: `${CHART_COLORS[i % CHART_COLORS.length]}20`,
      borderWidth: 2,
      fill: false,
      tension: 0.4,
      pointRadius: 4,
    })),
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: { color: dark ? '#94a3b8' : '#6b7280', font: { size: 11 } }
      },
      tooltip: { mode: 'index', intersect: false },
    },
    scales: {
      x: {
        ticks: { color: dark ? '#64748b' : '#9ca3af', font: { size: 10 } },
        grid: { color: dark ? '#1e293b' : '#f3f4f6' },
      },
      y: {
        ticks: { color: dark ? '#64748b' : '#9ca3af', font: { size: 10 } },
        grid: { color: dark ? '#1e293b' : '#f3f4f6' },
        beginAtZero: true,
      },
    },
  };

  const RISK_COLORS = {
    Critical: 'text-red-400 bg-red-500/20 border-red-500/30',
    High: 'text-orange-400 bg-orange-500/20 border-orange-500/30',
    Moderate: 'text-yellow-400 bg-yellow-500/20 border-yellow-500/30',
    Low: 'text-green-400 bg-green-500/20 border-green-500/30',
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className={`text-2xl font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>
            📈 Forecast &amp; Risk Analysis
          </h1>
          <p className={`text-sm mt-0.5 ${dark ? 'text-slate-400' : 'text-gray-500'}`}>
            Predictive analytics powered by statistical modelling + Google Gemini AI
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            id="forecast-months-select"
            value={months}
            onChange={e => setMonths(Number(e.target.value))}
            className={`text-sm px-3 py-2 rounded-xl border ${
              dark
                ? 'bg-slate-800 border-slate-600 text-slate-200'
                : 'bg-white border-gray-300 text-gray-700'
            }`}
          >
            <option value={1}>1 Month</option>
            <option value={3}>3 Months</option>
            <option value={6}>6 Months</option>
          </select>
          <button
            id="download-pdf-btn"
            onClick={downloadPdf}
            disabled={pdfLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium
                       bg-emerald-600 hover:bg-emerald-700 text-white transition disabled:opacity-50"
          >
            {pdfLoading ? '⟳ Generating…' : '📥 Download PDF'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">
          ⚠️ {error} — <button onClick={fetchForecast} className="underline">Retry</button>
        </div>
      )}

      {loading && !data && (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="w-12 h-12 rounded-full border-4 border-emerald-500/30 border-t-emerald-500 animate-spin" />
          <p className={`text-sm ${dark ? 'text-slate-400' : 'text-gray-500'}`}>
            Computing forecast…
          </p>
        </div>
      )}

      {data && (
        <>
          {/* Gemini Forecast Summary */}
          {gemini.forecast_summary && (
            <div className={`${card} border-l-4 border-l-emerald-500`}>
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center text-lg">
                  🤖
                </div>
                <div>
                  <h2 className={`text-sm font-semibold mb-1 ${dark ? 'text-white' : 'text-gray-900'}`}>
                    Gemini AI Forecast Summary
                  </h2>
                  <p className={`text-sm leading-relaxed ${dark ? 'text-slate-300' : 'text-gray-600'}`}>
                    {gemini.forecast_summary}
                  </p>
                  {gemini.seasonal_pattern && (
                    <p className={`text-xs mt-2 ${dark ? 'text-slate-500' : 'text-gray-400'}`}>
                      📅 {gemini.seasonal_pattern}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className={card}>
              <h2 className={`text-sm font-semibold mb-4 ${dark ? 'text-white' : 'text-gray-900'}`}>
                📊 Total Predicted Complaints (Monthly)
              </h2>
              <div style={{ height: 220 }}>
                <Bar data={barData} options={chartOptions} />
              </div>
            </div>
            <div className={card}>
              <h2 className={`text-sm font-semibold mb-4 ${dark ? 'text-white' : 'text-gray-900'}`}>
                📉 Category Trend Forecast
              </h2>
              <div style={{ height: 220 }}>
                <Line data={lineData} options={chartOptions} />
              </div>
            </div>
          </div>

          {/* High Risk Categories */}
          {(gemini.high_risk_categories || []).length > 0 && (
            <div className={card}>
              <h2 className={`text-base font-semibold mb-4 flex items-center gap-2 ${dark ? 'text-white' : 'text-gray-900'}`}>
                <span>🔥</span> High Risk Categories
                <span className={`ml-auto text-xs ${dark ? 'text-slate-500' : 'text-gray-400'}`}>
                  AI-identified surge risks
                </span>
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {gemini.high_risk_categories.map((item, i) => {
                  const colorClass = RISK_COLORS[item.risk_level] || RISK_COLORS.Moderate;
                  return (
                    <div key={i} className={`p-4 rounded-xl border ${colorClass}`}>
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-semibold text-sm">
                          {item.category?.replace(/_/g, ' ')}
                        </span>
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${colorClass}`}>
                          {item.risk_level}
                        </span>
                      </div>
                      <p className={`text-xs ${dark ? 'text-slate-400' : 'text-gray-500'}`}>
                        {item.reason}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Preventive Actions */}
          {(gemini.preventive_actions || []).length > 0 && (
            <div className={card}>
              <h2 className={`text-base font-semibold mb-4 flex items-center gap-2 ${dark ? 'text-white' : 'text-gray-900'}`}>
                <span>🛡️</span> Preventive Actions
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {gemini.preventive_actions.map((action, i) => (
                  <div key={i}
                       className={`flex items-start gap-3 p-3 rounded-xl ${
                         dark ? 'bg-slate-700/50' : 'bg-gray-50'
                       }`}>
                    <span className="text-emerald-400 flex-shrink-0 text-lg">✓</span>
                    <p className={`text-sm ${dark ? 'text-slate-300' : 'text-gray-700'}`}>{action}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Resource Recommendation */}
          {gemini.resource_recommendation && (
            <div className={`${card} border-l-4 border-l-amber-500`}>
              <div className="flex items-center gap-3">
                <span className="text-2xl">👥</span>
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-wider mb-1 ${
                    dark ? 'text-amber-400' : 'text-amber-600'
                  }`}>Resource Recommendation</p>
                  <p className={`text-sm ${dark ? 'text-slate-300' : 'text-gray-700'}`}>
                    {gemini.resource_recommendation}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Forecast Table */}
          <div className={card}>
            <h2 className={`text-base font-semibold mb-4 ${dark ? 'text-white' : 'text-gray-900'}`}>
              📋 Detailed Forecast Table
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className={dark ? 'text-slate-400 border-b border-slate-700' : 'text-gray-500 border-b border-gray-200'}>
                    <th className="text-left pb-3 font-medium">Category</th>
                    <th className="text-center pb-3 font-medium">Month</th>
                    <th className="text-center pb-3 font-medium">Predicted</th>
                    <th className="text-center pb-3 font-medium">Trend</th>
                    <th className="text-center pb-3 font-medium">Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-opacity-20">
                  {forecast.slice(0, 15).map((row, i) => (
                    <tr key={i} className={`${dark ? 'divide-slate-700/50 hover:bg-slate-700/30' : 'divide-gray-100 hover:bg-gray-50'} transition`}>
                      <td className={`py-3 font-medium ${dark ? 'text-slate-200' : 'text-gray-800'}`}>
                        {row.category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </td>
                      <td className={`py-3 text-center ${dark ? 'text-slate-400' : 'text-gray-500'}`}>{row.month}</td>
                      <td className={`py-3 text-center font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>
                        {row.predicted_count}
                      </td>
                      <td className="py-3 text-center">
                        <span className={row.trend > 0 ? 'text-red-400' : row.trend < 0 ? 'text-green-400' : 'text-slate-400'}>
                          {row.trend > 0 ? `↑ ${row.trend.toFixed(1)}` : row.trend < 0 ? `↓ ${Math.abs(row.trend).toFixed(1)}` : '→ 0'}
                        </span>
                      </td>
                      <td className="py-3 text-center">
                        <div className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                          row.confidence >= 80
                            ? dark ? 'bg-green-500/20 text-green-400' : 'bg-green-100 text-green-700'
                            : dark ? 'bg-yellow-500/20 text-yellow-400' : 'bg-yellow-100 text-yellow-700'
                        }`}>
                          {row.confidence}%
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
