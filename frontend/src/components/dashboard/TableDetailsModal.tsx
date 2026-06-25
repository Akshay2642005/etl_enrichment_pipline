import { X, ShieldCheck, Key, Hash, LayoutList } from 'lucide-react';
import type { NormalizedTable, QualityMetrics } from '../../lib/schema-adapter';

interface TableDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  table: NormalizedTable | null;
  metrics: QualityMetrics;
}

export const TableDetailsModal = ({ isOpen, onClose, table, metrics }: TableDetailsModalProps) => {
  if (!isOpen || !table) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl w-full max-w-5xl max-h-[85vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">{table.tableName}</h2>
            {table.description && (
              <p className="text-sm text-slate-500 mt-1">{table.description}</p>
            )}
          </div>
          <button 
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body: Split Left (Details) / Right (Quality) */}
        <div className="flex flex-1 overflow-hidden">
          
          {/* Left Panel: Table Details */}
          <div className="w-2/3 border-r border-slate-200 dark:border-slate-800 p-6 overflow-y-auto custom-scrollbar bg-white dark:bg-slate-900 space-y-6">
            
            {/* Columns */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                <LayoutList className="w-4 h-4" /> Columns ({table.columns.length})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {table.columns.map(col => (
                  <div key={col.columnName} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-semibold text-sm flex items-center gap-1.5 text-slate-800 dark:text-slate-200">
                        {col.isPrimaryKey && <Key className="w-3.5 h-3.5 text-amber-500" />}
                        {col.isForeignKey && <Key className="w-3.5 h-3.5 text-slate-400" />}
                        {!col.isPrimaryKey && !col.isForeignKey && <Hash className="w-3.5 h-3.5 text-slate-300" />}
                        {col.columnName}
                      </span>
                      <span className="text-xs font-mono text-blue-600 dark:text-blue-400">{col.dataType}</span>
                    </div>
                    <div className="flex gap-2 items-center flex-wrap">
                      {!col.nullable && <span className="text-[10px] px-1.5 py-0.5 bg-rose-100 text-rose-700 dark:bg-rose-900/30 rounded">NOT NULL</span>}
                      {col.semanticType && <span className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 dark:bg-amber-900/30 rounded">{col.semanticType}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Foreign Keys (Relationships) */}
            {table.relationships.length > 0 && (
              <div className="space-y-3 pt-2">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500">Foreign Keys (Outbound)</h3>
                <div className="space-y-2">
                  {table.relationships.map((rel, idx) => (
                    <div key={idx} className="flex items-center justify-between text-sm text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/30 p-3 border border-slate-100 dark:border-slate-800 rounded-lg">
                      <div><span className="font-semibold text-slate-800 dark:text-slate-200">{rel.childColumn}</span></div>
                      <div className="px-2 text-slate-400">&rarr;</div>
                      <div>{rel.parentTable}.<span className="font-semibold text-slate-800 dark:text-slate-200">{rel.parentColumn}</span></div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Referenced By (Inbound) */}
            {table.referencedBy.length > 0 && (
              <div className="space-y-3 pt-2">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500">Referenced By (Inbound)</h3>
                <div className="space-y-2">
                  {table.referencedBy.map((rel, idx) => (
                    <div key={idx} className="flex items-center justify-between text-sm text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/30 p-3 border border-slate-100 dark:border-slate-800 rounded-lg">
                      <div>{rel.childTable}.<span className="font-semibold text-slate-800 dark:text-slate-200">{rel.childColumn}</span></div>
                      <div className="px-2 text-slate-400">&rarr;</div>
                      <div><span className="font-semibold text-slate-800 dark:text-slate-200">{rel.parentColumn}</span></div>
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>

          {/* Right Panel: Quality Score */}
          <div className="w-1/3 bg-slate-50/50 dark:bg-slate-900/50 p-6 flex flex-col">
            <h3 className="text-sm font-bold tracking-tight text-slate-800 dark:text-slate-100 flex items-center gap-2 mb-6">
              <ShieldCheck className="w-4 h-4 text-emerald-500" />
              Schema Quality
            </h3>
            
            <div className="space-y-5">
              <div className="flex justify-between items-center p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-100 dark:border-slate-700 shadow-sm">
                <span className="text-sm text-slate-600 dark:text-slate-400 font-medium">Overall Score</span>
                <span className="text-lg font-bold text-slate-900 dark:text-slate-100">{metrics.overallScore}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-slate-500 font-medium">Completeness</span>
                <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">{metrics.completeness}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-slate-500 font-medium">Relationships</span>
                <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">{metrics.relationships}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-slate-500 font-medium">Naming Convention</span>
                <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">{metrics.naming}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-slate-500 font-medium">Documentation</span>
                <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">{metrics.documentation}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-slate-500 font-medium">Normalization</span>
                <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">{metrics.normalization}</span>
              </div>
            </div>

            <div className="mt-auto pt-6 border-t border-slate-200 dark:border-slate-800">
              <p className="text-xs text-slate-400 leading-relaxed">
                Quality metrics are evaluated based on LLM enrichment passes. These scores represent the holistic quality of your schema design.
              </p>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};
