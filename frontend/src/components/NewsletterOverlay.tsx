import { useState } from 'react';
import { Target, TrendingUp, ArrowRight, Zap, Database } from 'lucide-react';

const DUMMY_KPIS = [
  {
    name: 'On-Time Turnaround Rate',
    category: 'Operations',
    description: 'Percentage of turnaround operations completed on or before their target departure time.',
    potential_value: 'Reduces flight delays by 20%, saving penalty costs and improving airline SLA revenue.'
  },
  {
    name: 'Lost Baggage Rate',
    category: 'Customer Service',
    description: 'Percentage of total baggage items that have been reported as lost or delayed.',
    potential_value: 'Reduces compensation costs by $500K/year and improves passenger satisfaction scores.'
  },
  {
    name: 'Equipment Availability Rate',
    category: 'Equipment',
    description: 'Percentage of equipment items currently operational and available for assignment.',
    potential_value: 'Improves asset utilization by 15% and reduces emergency rental costs.'
  }
];

export const NewsletterOverlay = () => {
  const [isVisible, setIsVisible] = useState(true);

  if (!isVisible) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-slate-950 text-slate-100 overflow-y-auto">
      {/* Hero Section */}
      <div className="relative pt-6 pb-6 px-8 text-center bg-gradient-to-b from-slate-900 to-slate-950 border-b border-cyan-900/30">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute left-1/2 top-0 -translate-x-1/2 w-[800px] h-[300px] opacity-20">
            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500 to-blue-500 blur-[80px] rounded-full mix-blend-screen" />
          </div>
        </div>
        
        <div className="relative max-w-4xl mx-auto flex flex-col items-center">
          <img src="/logo1-removebg-preview.png" alt="HALO Logo" className="h-28 mb-4 drop-shadow-[0_0_20px_rgba(6,182,212,0.6)] hover:scale-105 transition-transform duration-300" />
          
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-cyan-500/10 text-cyan-300 font-medium text-xs mb-3 border border-cyan-500/20">
            <Zap className="w-3.5 h-3.5 text-cyan-400" />
            Your Daily Business Insights
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight mb-2 text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">
            Welcome Back to HALO
          </h1>
          <p className="text-base text-slate-400 max-w-2xl mx-auto">
            Before you dive into the data, here are the key performance indicators you're tracking. 
            Stay informed and make data-driven decisions.
          </p>
        </div>
      </div>

      {/* Content Section */}
      <div className="flex-1 max-w-5xl mx-auto w-full px-8 py-6">
        <div className="flex items-center gap-3 mb-4">
          <TrendingUp className="w-5 h-5 text-emerald-400" />
          <h2 className="text-xl font-bold text-white">Tracked KPIs</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {DUMMY_KPIS.map((kpi, idx) => (
            <div key={idx} className="group bg-slate-900/80 backdrop-blur-sm border border-slate-800 hover:border-cyan-500/50 rounded-2xl p-5 transition-all duration-300 hover:shadow-[0_0_30px_-5px_rgba(6,182,212,0.15)] hover:-translate-y-1 relative overflow-hidden flex flex-col">
              <div className="absolute top-0 right-0 p-3 opacity-10 group-hover:opacity-20 transition-opacity">
                <Target className="w-20 h-20 text-cyan-400" />
              </div>
              
              <div className="relative z-10 flex-1 flex flex-col">
                <div className="inline-block self-start px-2 py-1 rounded-md bg-blue-500/10 text-blue-400 text-[10px] font-bold uppercase tracking-wider mb-2 border border-blue-500/20">
                  {kpi.category}
                </div>
                <h3 className="text-lg font-bold text-white mb-2">{kpi.name}</h3>
                <p className="text-slate-400 text-xs mb-4 leading-relaxed flex-1">
                  {kpi.description}
                </p>
                
                <div className="bg-slate-950/50 rounded-xl p-3 border border-slate-800/50 backdrop-blur-md mt-auto group-hover:bg-slate-900/80 transition-colors">
                  <div className="flex items-center gap-2 text-[10px] font-medium text-emerald-400 mb-1">
                    <Database className="w-3 h-3" /> 
                    <span>POTENTIAL VALUE</span>
                  </div>
                  <div className="text-slate-200 font-medium text-xs">
                    {kpi.potential_value}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
        
        {/* Actions */}
        <div className="mt-8 text-center pb-6">
          <button
            onClick={() => setIsVisible(false)}
            className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-500 text-white hover:from-cyan-400 hover:to-blue-400 rounded-full font-bold shadow-[0_0_20px_rgba(6,182,212,0.4)] transition-all hover:scale-105 active:scale-95"
          >
            Continue to Dashboard
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
