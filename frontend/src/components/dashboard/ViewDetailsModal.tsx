import { X, Eye, LayoutList } from 'lucide-react';
import type { NormalizedView } from '../../lib/schema-adapter';

interface ViewDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  view: NormalizedView | null;
}

export const ViewDetailsModal = ({ isOpen, onClose, view }: ViewDetailsModalProps) => {
  if (!isOpen || !view) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
          <div className="flex items-center gap-2">
            <Eye className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">{view.viewName}</h2>
          </div>
          <button 
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex flex-col flex-1 overflow-y-auto custom-scrollbar p-6 space-y-6 bg-white dark:bg-slate-900">
          
          {/* SQL Definition */}
          {view.definition && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500">SQL Definition</h3>
              <pre className="p-4 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 text-sm font-mono text-slate-700 dark:text-slate-300 overflow-x-auto whitespace-pre-wrap">
                {view.definition.trim()}
              </pre>
            </div>
          )}

          {/* Columns */}
          {view.columns && view.columns.length > 0 && (
            <div className="space-y-3 pt-2">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                <LayoutList className="w-4 h-4" /> Columns ({view.columns.length})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {view.columns.map(col => (
                  <div key={col.columnName} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm text-slate-800 dark:text-slate-200">
                        {col.columnName}
                      </span>
                      <span className="text-xs font-mono text-blue-600 dark:text-blue-400">{col.dataType}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};
