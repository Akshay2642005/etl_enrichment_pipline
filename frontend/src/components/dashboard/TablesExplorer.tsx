import React, { useState } from 'react';
import type { Database } from '../../models/metadata';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Key, Type, ChevronDown, ChevronRight, Link as LinkIcon, AlertCircle } from 'lucide-react';

export const TablesExplorer = ({ database }: { database: Database }) => {
  const [expandedCol, setExpandedCol] = useState<string | null>(null);

  const toggleExpand = (tableId: string, colName: string) => {
    const key = `${tableId}-${colName}`;
    setExpandedCol(expandedCol === key ? null : key);
  };
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-2 gap-6">
      {database.tables.map((table, idx) => (
        <Card key={idx} className="border-slate-200 dark:border-slate-800 shadow-sm flex flex-col h-full hover:shadow-md transition-shadow">
          <CardHeader className="bg-slate-50/50 dark:bg-slate-900/50 border-b border-slate-100 dark:border-slate-800 pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-900/50 text-blue-600 flex items-center justify-center">
                  <Type className="w-4 h-4" />
                </div>
                {table.table_name}
              </CardTitle>
              <Badge variant="secondary" className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                {table.columns.length} Cols
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <div className="w-full">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-slate-500 uppercase bg-slate-50/80 dark:bg-slate-900/80 sticky top-0 backdrop-blur-sm z-10">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Column Name</th>
                    <th className="px-4 py-3 font-semibold">Data Type</th>
                    <th className="px-4 py-3 font-semibold text-center">Nullable</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {table.columns.map((col, cIdx) => {
                    const isPK = table.constraints?.some(c => c.constraint_type === 'PRIMARY KEY' && c.column_name === col.column_name);
                    const isFK = table.constraints?.some(c => c.constraint_type === 'FOREIGN KEY' && c.column_name === col.column_name);
                    
                    const colConstraints = table.constraints?.filter(c => c.column_name === col.column_name) || [];
                    const colRelationships = table.relationships?.filter(r => r.child_column === col.column_name) || [];
                    
                    const isExpanded = expandedCol === `${table.table_name}-${col.column_name}`;
                    const hasDetails = colConstraints.length > 0 || colRelationships.length > 0;
                    
                    return (
                      <React.Fragment key={cIdx}>
                        <tr 
                          onClick={() => hasDetails && toggleExpand(table.table_name, col.column_name)}
                          className={`group transition-colors ${hasDetails ? 'cursor-pointer hover:bg-slate-50/80 dark:hover:bg-slate-800/50' : 'hover:bg-slate-50/50 dark:hover:bg-slate-800/30'} ${isExpanded ? 'bg-slate-50 dark:bg-slate-800/40' : ''}`}
                        >
                          <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300 flex items-center gap-2">
                            {hasDetails ? (
                              isExpanded ? <ChevronDown className="w-3 h-3 text-slate-400" /> : <ChevronRight className="w-3 h-3 text-slate-400" />
                            ) : (
                              <div className="w-3 h-3" />
                            )}
                            {isPK && <Key className="w-3 h-3 text-amber-500" />}
                            {isFK && <Key className="w-3 h-3 text-slate-400" />}
                            {!isPK && !isFK && <div className="w-3 h-3" />}
                            {col.column_name}
                          </td>
                          <td className="px-4 py-2.5 font-mono text-xs text-blue-600 dark:text-blue-400">
                            {col.data_type}
                          </td>
                          <td className="px-4 py-2.5 text-center">
                            {col.nullable ? (
                              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600">✓</span>
                            ) : (
                              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400">-</span>
                            )}
                          </td>
                        </tr>
                        
                        {isExpanded && hasDetails && (
                          <tr className="bg-slate-50/50 dark:bg-slate-800/20 border-b border-slate-100 dark:border-slate-800">
                            <td colSpan={3} className="px-4 py-3">
                              <div className="pl-6 space-y-3">
                                {colConstraints.length > 0 && (
                                  <div className="space-y-1.5">
                                    <div className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
                                      <AlertCircle className="w-3 h-3" /> Constraints
                                    </div>
                                    <div className="space-y-1">
                                      {colConstraints.map((c, i) => (
                                        <div key={i} className="flex items-center gap-2 text-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 px-2.5 py-1.5 rounded-md">
                                          <span className="font-mono text-slate-500">{c.constraint_type}</span>
                                          <span className="text-slate-400">&middot;</span>
                                          <span className="text-slate-700 dark:text-slate-300">{c.constraint_name}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                
                                {colRelationships.length > 0 && (
                                  <div className="space-y-1.5">
                                    <div className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
                                      <LinkIcon className="w-3 h-3" /> Relationships
                                    </div>
                                    <div className="space-y-1">
                                      {colRelationships.map((r, i) => (
                                        <div key={i} className="flex items-center gap-2 text-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 px-2.5 py-1.5 rounded-md">
                                          <span className="text-slate-500">References</span>
                                          <span className="font-medium text-blue-600 dark:text-blue-400">{r.parent_table}</span>
                                          <span className="text-slate-400">({r.parent_column})</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ))}

      {database.views && database.views.map((view, idx) => (
        <Card key={`view-${idx}`} className="border-slate-200 dark:border-slate-800 shadow-sm flex flex-col h-full hover:shadow-md transition-shadow bg-slate-50/30 dark:bg-slate-900/30">
          <CardHeader className="bg-slate-100/50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700 pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/50 text-emerald-600 flex items-center justify-center">
                  <Type className="w-4 h-4" />
                </div>
                {view.view_name} <span className="text-xs font-normal text-slate-500">(View)</span>
              </CardTitle>
              <Badge variant="secondary" className="bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                {view.columns.length} Cols
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <div className="w-full">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-slate-500 uppercase bg-slate-100/80 dark:bg-slate-800/80 sticky top-0 backdrop-blur-sm z-10">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Column Name</th>
                    <th className="px-4 py-3 font-semibold">Data Type</th>
                    <th className="px-4 py-3 font-semibold text-center">Nullable</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {view.columns.map((col, cIdx) => (
                    <tr key={cIdx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors group">
                      <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300 flex items-center gap-2">
                        <div className="w-3 h-3" />
                        {col.column_name}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-emerald-600 dark:text-emerald-400">
                        {col.data_type}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {col.nullable ? (
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600">✓</span>
                        ) : (
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};
