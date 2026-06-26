import { useState, useMemo } from 'react';
import { useLocation, Navigate } from 'react-router-dom';
import { InteractiveGraph } from '../components/diagram/InteractiveGraph';
import { TableDetailsModal } from '../components/dashboard/TableDetailsModal';
import { ViewDetailsModal } from '../components/dashboard/ViewDetailsModal';
import { normalizeSchema } from '../lib/schema-adapter';
import type { NormalizedTable, NormalizedView } from '../lib/schema-adapter';
import { Database, Table as TableIcon, LayoutDashboard, ChevronDown, ChevronRight, Eye, Search } from 'lucide-react';
import { Card, CardContent } from '../components/ui/card';

export const SchemaView = () => {
  const location = useLocation();
  const rawMetadata = location.state?.metadata;
  
  const [selectedTable, setSelectedTable] = useState<NormalizedTable | null>(null);
  const [selectedView, setSelectedView] = useState<NormalizedView | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isViewModalOpen, setIsViewModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'graph'>('overview');
  const [tablesExpanded, setTablesExpanded] = useState(true);
  const [viewsExpanded, setViewsExpanded] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Memoize the normalized schema
  const schema = useMemo(() => {
    if (!rawMetadata) return null;
    return normalizeSchema(rawMetadata);
  }, [rawMetadata]);

  if (!schema) {
    return <Navigate to="/" replace />;
  }

  // Precompute Overview Stats
  const stats = useMemo(() => {
    let totalCols = 0;
    let totalPKs = 0;
    let totalFKs = 0;
    schema.tables.forEach(t => {
      totalCols += t.columns.length;
      totalPKs += t.columns.filter(c => c.isPrimaryKey).length;
      totalFKs += t.columns.filter(c => c.isForeignKey).length;
    });
    return {
      totalTables: schema.tables.length,
      totalViews: schema.views.length,
      totalCols,
      totalRels: schema.globalRelationships.length,
      totalPKs,
      totalFKs,
      totalIndexes: 'N/A' // Not extracted
    };
  }, [schema]);

  const handleSidebarTableSelect = (t: NormalizedTable) => {
    setSelectedTable(t);
    setActiveTab('graph');
  };

  const handleGraphNodeClick = (t: NormalizedTable) => {
    // Optionally change the center node as well, or just open the modal
    setSelectedTable(t);
    setIsModalOpen(true);
  };

  const filteredTables = schema.tables.filter(t => t.tableName.toLowerCase().includes(searchQuery.toLowerCase()));
  const filteredViews = schema.views.filter(v => v.viewName.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-50 overflow-hidden">
      
      {/* Left Sidebar */}
      <aside className="w-72 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col z-10 shadow-sm h-full">
        <div className="p-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/30">
              <Database className="w-4 h-4 text-white" />
            </div>
            <div>
              <h2 className="font-bold text-[15px] tracking-tight truncate w-48">{schema.schemaName}</h2>
              <p className="text-[11px] text-slate-500 font-medium uppercase tracking-wider">{schema.databaseType}</p>
            </div>
          </div>
          
          <button
            onClick={() => { setActiveTab('overview'); setSelectedTable(null); }}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'overview' 
                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300' 
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" /> Schema Overview
          </button>
        </div>

        <div className="p-3 border-b border-slate-200 dark:border-slate-800">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-slate-400" />
            <input 
              type="text" 
              placeholder="Filter objects..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-100 dark:bg-slate-800 border-0 rounded-md py-2 pl-9 pr-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {/* Tables Section */}
          <div className="py-2">
            <button 
              onClick={() => setTablesExpanded(!tablesExpanded)}
              className="w-full flex items-center justify-between px-4 py-1.5 text-xs font-bold text-slate-500 uppercase tracking-wider hover:text-slate-700 dark:hover:text-slate-300"
            >
              <span className="flex items-center gap-1.5">Tables ({filteredTables.length})</span>
              {tablesExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            </button>
            {tablesExpanded && (
              <div className="mt-1">
                {filteredTables.map(t => (
                  <button
                    key={t.tableName}
                    onClick={() => handleSidebarTableSelect(t)}
                    className={`w-full flex items-center gap-2 px-6 py-1.5 text-sm transition-colors ${
                      selectedTable?.tableName === t.tableName 
                        ? 'bg-blue-50 text-blue-700 font-semibold border-r-2 border-blue-600 dark:bg-blue-900/30 dark:text-blue-400' 
                        : 'text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800/50'
                    }`}
                  >
                    <TableIcon className="w-3.5 h-3.5 opacity-70" />
                    <span className="truncate">{t.tableName}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Views Section */}
          {filteredViews.length > 0 && (
            <div className="py-2 border-t border-slate-100 dark:border-slate-800/50">
              <button 
                onClick={() => setViewsExpanded(!viewsExpanded)}
                className="w-full flex items-center justify-between px-4 py-1.5 text-xs font-bold text-slate-500 uppercase tracking-wider hover:text-slate-700 dark:hover:text-slate-300"
              >
                <span className="flex items-center gap-1.5">Views ({filteredViews.length})</span>
                {viewsExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              </button>
              {viewsExpanded && (
                <div className="mt-1">
                  {filteredViews.map(v => (
                    <button
                      key={v.viewName}
                      onClick={() => { setSelectedView(v); setIsViewModalOpen(true); }}
                      className="w-full flex items-center gap-2 px-6 py-1.5 text-sm text-emerald-700 dark:text-emerald-400 opacity-80 hover:opacity-100 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span className="truncate">{v.viewName}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>

      {/* Center Panel */}
      <main className="flex-1 relative bg-slate-50 dark:bg-slate-950 flex flex-col">
        {activeTab === 'overview' ? (
          <div className="flex-1 overflow-y-auto p-8">
            <div className="max-w-4xl mx-auto space-y-6">
              <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Schema Overview</h1>
                <p className="text-slate-500 mt-1">Global statistics and structural summary of the extracted database metadata.</p>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: 'Database Name', value: schema.schemaName },
                  { label: 'Database Type', value: schema.databaseType },
                  { label: 'Total Tables', value: stats.totalTables },
                  { label: 'Total Views', value: stats.totalViews },
                  { label: 'Total Columns', value: stats.totalCols },
                  { label: 'Relationships', value: stats.totalRels },
                  { label: 'Primary Keys', value: stats.totalPKs },
                  { label: 'Foreign Keys', value: stats.totalFKs },
                ].map((s, i) => (
                  <Card key={i} className="shadow-sm border-slate-200 dark:border-slate-800">
                    <CardContent className="p-4">
                      <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">{s.label}</p>
                      <p className="text-xl font-bold text-slate-800 dark:text-slate-100 truncate">{s.value}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>

              <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                <TableIcon className="w-12 h-12 mb-4 opacity-20" />
                <p className="text-sm font-medium">Select a table from the sidebar to explore the knowledge graph</p>
              </div>
            </div>
          </div>
        ) : (
          <InteractiveGraph 
            schema={schema} 
            selectedTable={selectedTable} 
            onNodeClick={handleGraphNodeClick} 
          />
        )}
      </main>

      {/* Table Details Modal */}
      <TableDetailsModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        table={selectedTable} 
        metrics={schema.metrics} 
      />

      {/* View Details Modal */}
      <ViewDetailsModal 
        isOpen={isViewModalOpen}
        onClose={() => setIsViewModalOpen(false)}
        view={selectedView}
      />

    </div>
  );
};
