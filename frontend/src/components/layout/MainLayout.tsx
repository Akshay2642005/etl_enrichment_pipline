import { Outlet, NavLink } from 'react-router-dom';
import { Plug, FileJson, Lightbulb, Bot, BarChart } from 'lucide-react';

export const MainLayout = () => {
  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950 overflow-hidden">
      {/* Global Sidebar */}
      <aside className="w-64 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col z-20 shadow-sm">
        <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-center gap-3">
          <div className="bg-blue-600 rounded-lg p-2 flex items-center justify-center">
            <BarChart className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-lg font-bold text-slate-800 dark:text-slate-100 tracking-tight">
            HALO
          </h1>
        </div>

        <nav className="flex-1 overflow-y-auto py-6 px-4 space-y-2">
          <NavLink
            to="/connection"
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${isActive
                ? 'bg-blue-50 text-blue-700 font-semibold dark:bg-blue-900/30 dark:text-blue-400 shadow-sm border border-blue-100 dark:border-blue-800'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200'
              }`
            }
          >
            <Plug className="w-5 h-5" />
            Connection
          </NavLink>

          <NavLink
            to="/schema"
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${isActive
                ? 'bg-blue-50 text-blue-700 font-semibold dark:bg-blue-900/30 dark:text-blue-400 shadow-sm border border-blue-100 dark:border-blue-800'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200'
              }`
            }
          >
            <FileJson className="w-5 h-5" />
            Schema
          </NavLink>

          <NavLink
            to="/insights"
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${isActive
                ? 'bg-blue-50 text-blue-700 font-semibold dark:bg-blue-900/30 dark:text-blue-400 shadow-sm border border-blue-100 dark:border-blue-800'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200'
              }`
            }
          >
            <Lightbulb className="w-5 h-5" />
            Insights
          </NavLink>

          <NavLink
            to="/sql-agent"
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${isActive
                ? 'bg-blue-50 text-blue-700 font-semibold dark:bg-blue-900/30 dark:text-blue-400 shadow-sm border border-blue-100 dark:border-blue-800'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200'
              }`
            }
          >
            <Bot className="w-5 h-5" />
            Matrixes
          </NavLink>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 relative overflow-hidden bg-slate-50 dark:bg-slate-950 flex flex-col">
        <Outlet />
      </main>
    </div>
  );
};
