import { Bot } from 'lucide-react';

export const SqlAgentView = () => {
  return (
    <div className="flex flex-col items-center justify-center h-full text-slate-500 dark:text-cyan-100/50 bg-transparent w-full">
      <Bot className="w-16 h-16 mb-4 opacity-20" />
      <h2 className="text-xl font-semibold mb-2 text-slate-800 dark:text-cyan-50">SQL Agent</h2>
      <p className="text-sm font-medium">Coming soon! The SQL Agent backend is currently not set up.</p>
    </div>
  );
};
