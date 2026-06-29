import { Outlet, NavLink } from 'react-router-dom';
import { Plug, FileJson, Lightbulb, Bot, Menu } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';

export const MainLayout = () => {
  const isCollapsed = useAppStore((s) => s.sidebarCollapsed);
  const setIsCollapsed = useAppStore((s) => s.setSidebarCollapsed);

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-[#020617] overflow-hidden text-slate-900 dark:text-slate-50">
      {/* Global Sidebar */}
      <aside className={`${isCollapsed ? 'w-20' : 'w-64'} transition-all duration-300 ease-in-out bg-white dark:bg-[#0F172A]/80 backdrop-blur-xl border-r border-slate-200 dark:border-cyan-900/30 flex flex-col z-20 shadow-sm relative flex-shrink-0`}>
        <div className="absolute inset-0 pointer-events-none bg-gradient-to-b from-cyan-900/5 to-transparent z-0" />
        <div className={`p-2 px-4 border-b border-slate-200 dark:border-cyan-900/30 flex items-center ${isCollapsed ? 'justify-center py-6' : 'justify-between'} relative z-10 min-h-[96px]`}>
          {!isCollapsed && (
            <img src="/logo1-removebg-preview.png" alt="HALO AI AGENT SOFTWARE" className="h-16 md:h-20 object-contain drop-shadow-[0_0_8px_rgba(0,229,255,0.3)]" />
          )}
          <button 
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-2 rounded-xl text-slate-500 hover:bg-slate-100 dark:text-cyan-100/70 dark:hover:bg-[#081120]/50 transition-colors"
            title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          >
            <Menu className="w-6 h-6" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-6 px-4 space-y-2 relative z-10 custom-scrollbar">
          <NavLink
            to="/connection"
            className={({ isActive }) =>
              `flex items-center ${isCollapsed ? 'justify-center px-0' : 'gap-3 px-4'} py-3 rounded-xl transition-all duration-300 ${isActive
                ? 'bg-blue-50 text-cyan-600 font-semibold dark:bg-cyan-950/40 dark:text-cyan-400 shadow-[0_0_15px_rgba(0,229,255,0.15)] border border-blue-100 dark:border-cyan-800/50'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-cyan-100 border border-transparent'
              }`
            }
            title={isCollapsed ? "Connection" : undefined}
          >
            <Plug className="w-5 h-5 flex-shrink-0" />
            {!isCollapsed && <span className="truncate">Connection</span>}
          </NavLink>

          <NavLink
            to="/schema"
            className={({ isActive }) =>
              `flex items-center ${isCollapsed ? 'justify-center px-0' : 'gap-3 px-4'} py-3 rounded-xl transition-all duration-300 ${isActive
                ? 'bg-blue-50 text-cyan-600 font-semibold dark:bg-cyan-950/40 dark:text-cyan-400 shadow-[0_0_15px_rgba(0,229,255,0.15)] border border-blue-100 dark:border-cyan-800/50'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-cyan-100 border border-transparent'
              }`
            }
            title={isCollapsed ? "Schema" : undefined}
          >
            <FileJson className="w-5 h-5 flex-shrink-0" />
            {!isCollapsed && <span className="truncate">Schema</span>}
          </NavLink>

          <NavLink
            to="/insights"
            className={({ isActive }) =>
              `flex items-center ${isCollapsed ? 'justify-center px-0' : 'gap-3 px-4'} py-3 rounded-xl transition-all duration-300 ${isActive
                ? 'bg-blue-50 text-cyan-600 font-semibold dark:bg-cyan-950/40 dark:text-cyan-400 shadow-[0_0_15px_rgba(0,229,255,0.15)] border border-blue-100 dark:border-cyan-800/50'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-cyan-100 border border-transparent'
              }`
            }
            title={isCollapsed ? "Insights" : undefined}
          >
            <Lightbulb className="w-5 h-5 flex-shrink-0" />
            {!isCollapsed && <span className="truncate">Insights</span>}
          </NavLink>

          <NavLink
            to="/sql-agent"
            className={({ isActive }) =>
              `flex items-center ${isCollapsed ? 'justify-center px-0' : 'gap-3 px-4'} py-3 rounded-xl transition-all duration-300 ${isActive
                ? 'bg-blue-50 text-cyan-600 font-semibold dark:bg-cyan-950/40 dark:text-cyan-400 shadow-[0_0_15px_rgba(0,229,255,0.15)] border border-blue-100 dark:border-cyan-800/50'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-cyan-100 border border-transparent'
              }`
            }
            title={isCollapsed ? "Matrices" : undefined}
          >
            <Bot className="w-5 h-5 flex-shrink-0" />
            {!isCollapsed && <span className="truncate">Matrices</span>}
          </NavLink>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 relative overflow-hidden bg-slate-50 dark:bg-[#020617] flex flex-col">
        {/* Subtle grid background effect */}
        <div className="absolute inset-0 z-0 pointer-events-none opacity-[0.03] dark:opacity-[0.05]" style={{ backgroundImage: 'linear-gradient(#00E5FF 1px, transparent 1px), linear-gradient(90deg, #00E5FF 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
        <div className="absolute inset-0 z-0 pointer-events-none bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/10 via-transparent to-transparent dark:from-cyan-900/20 dark:via-[#081120]/80 dark:to-[#020617]" />
        
        <div className="relative z-10 flex-1 flex flex-col overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
