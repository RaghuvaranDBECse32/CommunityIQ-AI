import { LayoutDashboard, FileText, BarChart3,
         ChevronLeft, ChevronRight, Brain, TrendingUp, Shield } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

const NAV = [
  { id: 'overview',    label: 'Overview',     icon: LayoutDashboard },
  { id: 'complaints',  label: 'Complaints',   icon: FileText },
  { id: 'analytics',  label: 'Analytics',    icon: BarChart3 },
  { id: 'decision',   label: 'Intelligence', icon: Brain },
  { id: 'forecast',   label: 'Forecast',     icon: TrendingUp },
];

export default function Sidebar({ tab, setTab, open, setOpen }) {
  const { theme, toggle } = useTheme();
  const dark = theme === 'dark';

  return (
    <>
      {/* ── Desktop sidebar (md and up) ── */}
      <aside className={`hidden md:flex fixed top-0 left-0 h-screen
                         border-r flex-col
                         transition-all duration-300 z-20
                         ${dark
                           ? 'bg-[#0d1321] border-[#1e293b]'
                           : 'bg-white border-gray-200 shadow-lg'
                         }
                         ${open ? 'w-60' : 'w-16'}`}>

        {/* Brand */}
        <div className={`px-4 py-5 flex items-center gap-3 border-b ${dark ? 'border-[#1e293b]' : 'border-gray-200'}`}>
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500
                          to-violet-600 flex items-center justify-center
                          shadow-lg shadow-blue-500/25 flex-shrink-0">
            <Brain size={18} className="text-white" />
          </div>
          {open && (
            <div className="overflow-hidden">
              <h1 className={`text-sm font-bold tracking-tight whitespace-nowrap ${dark ? 'text-white' : 'text-gray-900'}`}>
                CommunityIQ AI
              </h1>
              <p className={`text-[10px] whitespace-nowrap ${dark ? 'text-slate-500' : 'text-gray-400'}`}>
                Decision Intelligence
              </p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-2 space-y-1">
          {NAV.map(item => {
            const Icon = item.icon;
            const active = tab === item.id;
            // Special badge for Decision Intelligence
            const isNew = item.id === 'decision' || item.id === 'forecast';
            return (
              <button key={item.id}
                id={`nav-${item.id}`}
                onClick={() => setTab(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5
                           rounded-xl text-sm font-medium transition-all group
                           ${active
                             ? dark
                               ? 'bg-blue-600/20 text-blue-400'
                               : 'bg-blue-50 text-blue-600'
                             : dark
                               ? 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                               : 'text-gray-500 hover:bg-gray-50 hover:text-gray-800'
                           }`}>
                <Icon size={18} className={active ? (dark ? 'text-blue-400' : 'text-blue-600') : ''} />
                {open && (
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="whitespace-nowrap">{item.label}</span>
                    {isNew && (
                      <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded-full
                                       bg-blue-500 text-white font-bold tracking-wide">
                        AI
                      </span>
                    )}
                  </div>
                )}
              </button>
            );
          })}
        </nav>

        {/* Dark mode toggle */}
        <div className={`px-3 pb-2 border-t ${dark ? 'border-[#1e293b]' : 'border-gray-200'}`}>
          <button
            id="theme-toggle-btn"
            onClick={toggle}
            className={`w-full flex items-center gap-3 px-3 py-2.5 mt-2
                       rounded-xl text-sm transition-all
                       ${dark
                         ? 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                         : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'}`}>
            <span>{dark ? '☀️' : '🌙'}</span>
            {open && <span>{dark ? 'Light Mode' : 'Dark Mode'}</span>}
          </button>
        </div>

        {/* Collapse toggle */}
        <div className={`p-3 border-t ${dark ? 'border-[#1e293b]' : 'border-gray-200'}`}>
          <button onClick={() => setOpen(!open)}
                  className={`w-full flex items-center justify-center gap-2
                             py-2 rounded-lg transition-colors text-xs
                             ${dark
                               ? 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
                               : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50'}`}>
            {open ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
            {open && 'Collapse'}
          </button>
        </div>

        {/* Officer badge */}
        {open && (
          <div className={`px-4 py-3 border-t flex items-center gap-3 ${dark ? 'border-[#1e293b]' : 'border-gray-200'}`}>
            <div className="w-8 h-8 rounded-full bg-gradient-to-br
                            from-emerald-500 to-emerald-700
                            flex items-center justify-center text-xs
                            font-bold text-white flex-shrink-0">MO</div>
            <div className="overflow-hidden">
              <p className={`text-xs font-medium truncate ${dark ? 'text-slate-200' : 'text-gray-800'}`}>
                Municipal Officer
              </p>
              <p className={`text-[10px] truncate ${dark ? 'text-slate-500' : 'text-gray-400'}`}>
                CommunityIQ AI
              </p>
            </div>
          </div>
        )}
      </aside>

      {/* ── Mobile bottom nav (below md) ── */}
      <nav className={`md:hidden fixed bottom-0 left-0 right-0 z-30
                      backdrop-blur-md border-t
                      flex items-center justify-around
                      h-14 px-1
                      ${dark
                        ? 'bg-[#0d1321]/95 border-[#1e293b]'
                        : 'bg-white/95 border-gray-200'}`}>
        {NAV.map(item => {
          const Icon = item.icon;
          const active = tab === item.id;
          return (
            <button key={item.id}
              onClick={() => setTab(item.id)}
              className={`flex flex-col items-center gap-0.5 px-2 py-1.5
                         rounded-lg transition-all active:scale-95 flex-1
                         ${active
                           ? dark ? 'text-blue-400' : 'text-blue-600'
                           : dark ? 'text-slate-500' : 'text-gray-400'}`}>
              <Icon size={18} />
              <span className="text-[9px] font-medium">{item.label}</span>
            </button>
          );
        })}
      </nav>
    </>
  );
}
