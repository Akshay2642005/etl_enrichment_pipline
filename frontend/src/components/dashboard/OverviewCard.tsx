import { Card, CardContent } from '../ui/card';
import { Database, Table as TableIcon, Link as LinkIcon, AlertCircle } from 'lucide-react';
import type { Database as DBType } from '../../models/metadata';

export const OverviewCard = ({ data }: { data: DBType }) => {
  let totalColumns = 0;
  let totalRelationships = 0;
  let totalConstraints = 0;

  data.tables.forEach(t => {
    totalColumns += t.columns.length;
    totalRelationships += t.relationships?.length || 0;
    totalConstraints += t.constraints?.length || 0;
  });

  const stats = [
    { label: 'Total Tables', value: data.tables.length, icon: TableIcon, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/50' },
    { label: 'Total Columns', value: totalColumns, icon: Database, color: 'text-indigo-500', bg: 'bg-indigo-100 dark:bg-indigo-900/50' },
    { label: 'Relationships', value: totalRelationships, icon: LinkIcon, color: 'text-violet-500', bg: 'bg-violet-100 dark:bg-violet-900/50' },
    { label: 'Constraints', value: totalConstraints, icon: AlertCircle, color: 'text-emerald-500', bg: 'bg-emerald-100 dark:bg-emerald-900/50' },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat, idx) => {
        const Icon = stat.icon;
        return (
          <Card key={idx} className="border-slate-200 dark:border-slate-800 shadow-sm">
            <CardContent className="p-6 flex items-center gap-4">
              <div className={`p-3 rounded-xl ${stat.bg}`}>
                <Icon className={`w-6 h-6 ${stat.color}`} />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{stat.label}</p>
                <h4 className="text-2xl font-bold text-slate-900 dark:text-slate-50">{stat.value}</h4>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
};
