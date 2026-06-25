import { Handle, Position } from '@xyflow/react';
import { Database, Key } from 'lucide-react';
import type { Table } from '../../models/metadata';

export const TableNode = ({ data }: { data: { table: Table } }) => {
  const { table } = data;
  const pks = table.constraints?.filter(c => c.constraint_type === 'PRIMARY KEY').map(c => c.column_name) || [];
  const fks = table.constraints?.filter(c => c.constraint_type === 'FOREIGN KEY').map(c => c.column_name) || [];

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg w-[280px] overflow-hidden">
      {/* Node Header */}
      <div className="bg-slate-50 dark:bg-slate-800 p-3 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-blue-500" />
          <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100">{table.table_name}</h3>
        </div>
        <span className="text-[10px] font-medium px-2 py-0.5 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded-full">
          {table.columns.length} cols
        </span>
      </div>

      {/* Columns List */}
      <div className="p-2 space-y-1">
        {table.columns.map((col, idx) => (
          <div key={idx} className="flex items-center justify-between text-xs px-2 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-800/50 rounded relative group">
            <div className="flex items-center gap-2">
              {pks.includes(col.column_name) ? (
                <Key className="w-3 h-3 text-amber-500" />
              ) : fks.includes(col.column_name) ? (
                <Key className="w-3 h-3 text-slate-400" />
              ) : (
                <div className="w-3 h-3" />
              )}
              <span className="font-medium text-slate-700 dark:text-slate-300">{col.column_name}</span>
            </div>
            <span className="font-mono text-slate-400 dark:text-slate-500 text-[10px]">{col.data_type}</span>
            
            {/* Handles for edges */}
            <Handle
              type="source"
              position={Position.Right}
              id={`source-${col.column_name}`}
              className="!w-2 !h-2 !bg-blue-400 !border-0 opacity-0 group-hover:opacity-100 transition-opacity"
              style={{ top: '50%' }}
            />
            <Handle
              type="target"
              position={Position.Left}
              id={`target-${col.column_name}`}
              className="!w-2 !h-2 !bg-indigo-400 !border-0 opacity-0 group-hover:opacity-100 transition-opacity"
              style={{ top: '50%' }}
            />
          </div>
        ))}
      </div>
    </div>
  );
};
