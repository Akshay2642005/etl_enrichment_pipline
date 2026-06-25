import { Lightbulb } from 'lucide-react';

export const InsightsView = () => {
  return (
    <div className="flex flex-col items-center justify-center h-full text-slate-400 bg-slate-50/50 dark:bg-slate-950/50">
      <Lightbulb className="w-16 h-16 mb-4 opacity-20" />
      <h2 className="text-xl font-bold text-slate-700 dark:text-slate-300 mb-2">Insights Dashboard</h2>
      <p className="text-sm font-medium">Coming soon! The Insights backend is currently not set up.</p>
    </div>
  );
};
