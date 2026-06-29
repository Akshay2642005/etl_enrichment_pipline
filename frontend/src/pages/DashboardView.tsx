import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { LayoutDashboard, Plus, Database, Clock, ArrowRight, Loader2, Server, Plug, Search, Filter } from 'lucide-react';
import { fetchSavedConnections, fetchConnectionDetails } from '../services/api';
import { useAppStore } from '../store/useAppStore';

interface SavedConnectionSummary {
  id: string;
  name: string;
  description: string | null;
  database_type: string;
  status: string;
  table_count: number;
  view_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export const DashboardView = () => {
  const navigate = useNavigate();
  const setMetadata = useAppStore(s => s.setMetadata);
  const setInsightsData = useAppStore(s => s.setInsightsData);
  const resetStore = useAppStore(s => s.reset);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoadingConnection, setIsLoadingConnection] = useState<string | null>(null);

  // Fetch summaries
  const { data: connections = [], isLoading, isError, refetch } = useQuery<SavedConnectionSummary[]>({
    queryKey: ['savedConnections'],
    queryFn: fetchSavedConnections,
  });

  const handleConnectionClick = async (id: string) => {
    setIsLoadingConnection(id);
    try {
      const details = await fetchConnectionDetails(id);
      
      // Store the connection ID for later insight persistence
      useAppStore.getState().setCurrentConnectionId(id);
      
      // Update store with fetched data so they don't have to re-extract/generate
      if (details.enriched_schema) {
        setMetadata(details.enriched_schema);
      }
      if (details.insights) {
        setInsightsData(details.insights);
      }
      
      // Redirect to Insights view where they can see the data
      navigate('/insights');
    } catch (err) {
      console.error('Failed to load connection details:', err);
    } finally {
      setIsLoadingConnection(null);
    }
  };

  const handleNewConnection = () => {
    resetStore();
    navigate('/connection');
  };

  const filteredConnections = connections.filter(c => 
    c.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    (c.description && c.description.toLowerCase().includes(searchQuery.toLowerCase())) ||
    c.database_type.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex-1 h-full overflow-auto bg-slate-50 dark:bg-[#020617] p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-800 dark:text-slate-100 mb-2 flex items-center gap-3">
              <LayoutDashboard className="w-8 h-8 text-cyan-500" />
              Overview Dashboard
            </h1>
            <p className="text-slate-600 dark:text-slate-400">
              Manage and analyze your active database connections and enriched metadata.
            </p>
          </div>
          
          <button 
            onClick={handleNewConnection}
            className="flex items-center gap-2 px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl font-medium shadow-md shadow-cyan-500/20 transition-all duration-200"
          >
            <Plus className="w-5 h-5" />
            New Connection
          </button>
        </div>

        {/* Toolbar */}
        <div className="flex flex-col md:flex-row gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input 
              type="text" 
              placeholder="Search connections..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            />
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg font-medium transition-colors">
            <Filter className="w-4 h-4" />
            Filter
          </button>
        </div>

        {/* Connections Grid */}
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="w-12 h-12 text-cyan-500 animate-spin mb-4" />
            <p className="text-slate-500 dark:text-slate-400">Loading saved connections...</p>
          </div>
        ) : isError ? (
          <div className="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 p-6 rounded-xl border border-red-100 dark:border-red-900/50 flex flex-col items-center text-center">
            <Server className="w-12 h-12 mb-3 opacity-50" />
            <h3 className="text-lg font-bold mb-1">Failed to load connections</h3>
            <p className="text-sm opacity-80 mb-4">Could not connect to the backend API.</p>
            <button onClick={() => refetch()} className="px-4 py-2 bg-red-100 dark:bg-red-800/50 rounded-lg font-medium hover:bg-red-200 dark:hover:bg-red-800 transition-colors">
              Try Again
            </button>
          </div>
        ) : filteredConnections.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 bg-white/50 dark:bg-slate-900/50 border border-dashed border-slate-300 dark:border-slate-700 rounded-2xl">
            <Plug className="w-16 h-16 text-slate-400 dark:text-slate-600 mb-4" />
            <h3 className="text-xl font-bold text-slate-700 dark:text-slate-300 mb-2">No connections found</h3>
            <p className="text-slate-500 dark:text-slate-400 max-w-md text-center mb-6">
              You haven't saved any database connections yet, or none match your search criteria.
            </p>
            <button onClick={handleNewConnection} className="flex items-center gap-2 px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl font-medium transition-all duration-200">
              <Plus className="w-5 h-5" />
              Create First Connection
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredConnections.map((conn) => (
              <div 
                key={conn.id}
                onClick={() => handleConnectionClick(conn.id)}
                className="group relative bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm hover:shadow-xl hover:border-cyan-300 dark:hover:border-cyan-700/50 transition-all duration-300 cursor-pointer overflow-hidden flex flex-col"
              >
                {/* Glow effect on hover */}
                <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/0 via-transparent to-transparent group-hover:from-cyan-500/5 dark:group-hover:from-cyan-500/10 transition-colors duration-500 pointer-events-none" />
                
                <div className="flex items-start justify-between mb-4 relative z-10">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center border border-slate-200 dark:border-slate-700">
                      <Database className="w-6 h-6 text-slate-600 dark:text-slate-400 group-hover:text-cyan-500 transition-colors" />
                    </div>
                    <div>
                      <h3 className="font-bold text-lg text-slate-800 dark:text-slate-100 group-hover:text-cyan-600 dark:group-hover:text-cyan-400 transition-colors line-clamp-1">
                        {conn.name}
                      </h3>
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 uppercase tracking-wider">
                        {conn.database_type}
                      </span>
                    </div>
                  </div>
                  <div className={`w-3 h-3 rounded-full shadow-sm ${conn.status === 'active' ? 'bg-emerald-500' : conn.status === 'error' ? 'bg-red-500' : 'bg-slate-400'}`} title={`Status: ${conn.status}`} />
                </div>
                
                <p className="text-sm text-slate-500 dark:text-slate-400 line-clamp-2 mb-6 flex-1 relative z-10">
                  {conn.description || 'No description provided.'}
                </p>
                
                <div className="flex items-center justify-between pt-4 border-t border-slate-100 dark:border-slate-800/50 mt-auto relative z-10">
                  <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
                    <div className="flex items-center gap-1" title="Tables / Views">
                      <Database className="w-3.5 h-3.5" />
                      {conn.table_count + conn.view_count} objects
                    </div>
                    <div className="flex items-center gap-1" title="Created At">
                      <Clock className="w-3.5 h-3.5" />
                      {conn.created_at ? new Date(conn.created_at).toLocaleDateString() : 'N/A'}
                    </div>
                  </div>
                  
                  <div className="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center group-hover:bg-cyan-100 dark:group-hover:bg-cyan-900/50 transition-colors">
                    {isLoadingConnection === conn.id ? (
                      <Loader2 className="w-4 h-4 text-cyan-600 dark:text-cyan-400 animate-spin" />
                    ) : (
                      <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-cyan-600 dark:group-hover:text-cyan-400 transition-colors" />
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
