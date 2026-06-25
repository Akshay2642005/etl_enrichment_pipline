import { useState } from 'react';
import { useLocation, Navigate } from 'react-router-dom';
import { OverviewCard } from '../components/dashboard/OverviewCard';
import { TablesExplorer } from '../components/dashboard/TablesExplorer';
import { ERDiagram } from '../components/diagram/ERDiagram';
import { LayoutDashboard, Database, Link as LinkIcon, Component } from 'lucide-react';

export const Dashboard = () => {
  const location = useLocation();
  const metadata = location.state?.metadata;
  const [activeTab, setActiveTab] = useState('overview');

  if (!metadata) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-50 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col z-10 shadow-sm">
        <div className="p-6 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/30">
              <Database className="w-4 h-4 text-white" />
            </div>
            <div>
              <h2 className="font-bold text-lg tracking-tight">ETL Platform</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">Schema Intelligence</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          <button
            onClick={() => setActiveTab('overview')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'overview' 
                ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' 
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" /> Overview
          </button>
          
          <button
            onClick={() => setActiveTab('tables')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'tables' 
                ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' 
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            <Component className="w-4 h-4" /> Tables & Columns
          </button>
          
          <button
            onClick={() => setActiveTab('er-diagram')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'er-diagram' 
                ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' 
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            <LinkIcon className="w-4 h-4" /> ER Diagram
          </button>
        </nav>
        
        <div className="p-4 border-t border-slate-200 dark:border-slate-800">
          <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-700">
            <p className="text-xs text-slate-500 mb-1 font-medium">Database Type</p>
            <p className="text-sm font-bold capitalize text-slate-800 dark:text-slate-200 flex items-center gap-2">
              <Database className="w-3 h-3 text-emerald-500" />
              {metadata.database_type || 'Unknown'}
            </p>
            <p className="text-xs text-slate-500 mt-2 font-medium">Schema</p>
            <p className="text-sm font-bold text-slate-800 dark:text-slate-200">{metadata.schema || 'public'}</p>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden">
        <header className="h-16 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md flex items-center justify-between px-8 z-10">
          <h1 className="text-xl font-bold tracking-tight text-slate-800 dark:text-slate-100 capitalize">
            {activeTab.replace('-', ' ')}
          </h1>
          <div className="flex items-center gap-4">
            <span className="text-sm font-medium text-slate-500 bg-slate-100 dark:bg-slate-800 px-3 py-1.5 rounded-full border border-slate-200 dark:border-slate-700">
              {metadata.tables.length} Tables Connected
            </span>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
          <div className="max-w-7xl mx-auto space-y-8">
            {activeTab === 'overview' && (
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <OverviewCard data={metadata} />
              </div>
            )}
            
            {activeTab === 'tables' && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                <TablesExplorer database={metadata} />
              </div>
            )}
            
            {activeTab === 'er-diagram' && (
              <div className="h-[800px] animate-in fade-in slide-in-from-bottom-4 duration-500 shadow-xl rounded-xl border border-slate-200/50 dark:border-slate-800/50">
                <ERDiagram database={metadata} />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};
