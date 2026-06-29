import { useEffect, useState } from 'react';
import { Target, Lightbulb, TrendingUp, Rocket, Loader2, RefreshCw, AlertCircle, Database, Server } from 'lucide-react';
import { generateInsights, fetchEmbeddingStatus } from '../services/api';
import { useAppStore } from '../store/useAppStore';

interface KPI {
  name: string;
  description: string;
  sql_query: string;
  category: string;
  potential_value: string;
}

interface Insight {
  finding: string;
  supporting_evidence: string;
  impact: string;
  confidence: number;
}

interface Opportunity {
  area: string;
  description: string;
  potential_value: string;
  effort: string;
  suggested_approach: string;
}

interface ArtOfThePossible {
  title: string;
  description: string;
  technologies_needed: string;
  complexity: string;
  business_value: string;
}

interface InsightsData {
  kpis: KPI[];
  insights: Insight[];
  opportunities: Opportunity[];
  art_of_the_possible: ArtOfThePossible[];
}

export const InsightsView = () => {
  const data = useAppStore((s) => s.insightsData);
  const setData = useAppStore((s) => s.setInsightsData);
  const isLoading = useAppStore((s) => s.insightsLoading);
  const setIsLoading = useAppStore((s) => s.setInsightsLoading);
  const error = useAppStore((s) => s.insightsError);
  const setError = useAppStore((s) => s.setInsightsError);
  const embeddingStatus = useAppStore((s) => s.embeddingStatus);
  const setEmbeddingStatus = useAppStore((s) => s.setEmbeddingStatus);
  const metadata = useAppStore((s) => s.metadata);
  
  const MAIN_TABS = ['KPIs', 'Data-Driven Insights', 'Operational Opportunities', 'Art of the Possible'];
  const CATEGORIES = ['Operations', 'Finance', 'Marketing', 'Sales', 'Human Resources', 'IT'];
  
  const [activeMainTab, setActiveMainTab] = useState<string>(MAIN_TABS[0]);
  const [activeCategory, setActiveCategory] = useState<string>(CATEGORIES[0]);

  // Normalize data so it supports a tabbed structure
  let currentTabsData: Record<string, InsightsData> = {};
  if (data) {
    if (data.kpis) {
      // Legacy flat structure
      currentTabsData = { [CATEGORIES[0]]: data as any };
    } else {
      currentTabsData = data as any;
    }
  }
  const currentCategoryData = currentTabsData[activeCategory] || null;

  useEffect(() => {
    if (!metadata || data) return;

    let cancelled = false;
    const poll = async () => {
      try {
        const status = await fetchEmbeddingStatus();
        if (!cancelled) setEmbeddingStatus(status);
      } catch {
        /* server unreachable */
      }
    };

    poll();
    const interval = setInterval(poll, 3000);
    const timeout = setTimeout(() => {
      cancelled = true;
      clearInterval(interval);
    }, 300_000);

    return () => {
      cancelled = true;
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [metadata, data, setEmbeddingStatus]);

  const handleGenerate = async () => {
    setIsLoading(true);
    setError(null);
    try {
      let current = { ...currentTabsData };
      
      // Generate for all domains sequentially so the UI updates progressively
      for (const cat of CATEGORIES) {
        try {
          const result = await generateInsights(cat);
          current = { ...current, [cat]: result };
          setData(current); // Update store progressively
        } catch (e) {
          console.error(`Failed to generate for ${cat}:`, e);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to generate insights.');
    } finally {
      setIsLoading(false);
    }
  };

  // Show embedding progress when metadata exists but nothing is loaded yet
  if (metadata && !data && !isLoading && !error && embeddingStatus.status === 'embedding') {
    return (
      <div className="flex flex-col items-center justify-center h-full max-w-lg mx-auto text-center px-4">
        <div className="w-20 h-20 bg-indigo-100 dark:bg-indigo-900/30 rounded-2xl flex items-center justify-center mb-6">
          <Server className="w-10 h-10 text-indigo-600 dark:text-indigo-400" />
        </div>
        <h2 className="text-3xl font-bold text-slate-800 dark:text-slate-100 mb-4">
          Embedding Schema Vectors
        </h2>
        <p className="text-slate-600 dark:text-slate-400 mb-8 text-lg">
          The enriched metadata is being vectorized and indexed into the knowledge stores.
          Insights generation will be available once indexing completes.
        </p>
        <div className="w-full max-w-sm bg-slate-200 dark:bg-slate-700 rounded-full h-2 mb-2 overflow-hidden">
          <div className="bg-indigo-500 h-2 rounded-full animate-pulse" style={{ width: '60%' }} />
        </div>
        <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">
          Indexing in progress&hellip;
        </p>
      </div>
    );
  }

  const hasAnyData = Object.keys(currentTabsData).length > 0;

  if (!hasAnyData && !isLoading && !error) {
    return (
      <div className="flex flex-col items-center justify-center h-full max-w-2xl mx-auto text-center px-4">
        <div className="w-20 h-20 bg-blue-100 dark:bg-blue-900/30 rounded-2xl flex items-center justify-center mb-6">
          <Lightbulb className="w-10 h-10 text-blue-600 dark:text-blue-400" />
        </div>
        <h2 className="text-3xl font-bold text-slate-800 dark:text-slate-100 mb-4">
          Enterprise Insights
        </h2>
        <p className="text-slate-600 dark:text-slate-400 mb-8 text-lg">
          Generate specialized KPIs, insights, and opportunities tailored specifically for Operations, Finance, and other domains across your enterprise.
        </p>
        {embeddingStatus.status === 'failed' && (
          <div className="mb-6 w-full max-w-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4 text-sm text-amber-700 dark:text-amber-400">
            <AlertCircle className="w-4 h-4 inline mr-1" />
            Background embedding encountered an error. Insights can still be generated from the enriched metadata directly.
          </div>
        )}
        <button
          onClick={handleGenerate}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium shadow-sm transition-colors"
        >
          <RefreshCw className="w-5 h-5" />
          Generate All Insights
        </button>
      </div>
    );
  }

  if (isLoading && !hasAnyData) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <Loader2 className="w-12 h-12 text-blue-600 animate-spin mb-4" />
        <h3 className="text-xl font-semibold text-slate-700 dark:text-slate-300">
          Generating Insights...
        </h3>
        <p className="text-slate-500 dark:text-slate-400 mt-2 max-w-md text-center">
          Our AI is analyzing the database schema, evaluating domain contexts, and synthesizing business intelligence. Generating for all domains may take a few moments.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full max-w-md mx-auto text-center px-4">
        <AlertCircle className="w-16 h-16 text-red-500 mb-4" />
        <h3 className="text-xl font-bold text-slate-800 dark:text-slate-100 mb-2">Error Generating Insights</h3>
        <p className="text-red-600 dark:text-red-400 mb-6 bg-red-50 dark:bg-red-900/20 p-4 rounded-lg w-full">
          {error}
        </p>
        <button
          onClick={handleGenerate}
          className="flex items-center gap-2 px-6 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg font-medium shadow-sm transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-800 dark:text-slate-100 mb-2 flex items-center gap-3">
            <Lightbulb className="w-8 h-8 text-yellow-500" />
            Schema Insights
          </h1>
          <p className="text-slate-600 dark:text-slate-400">
            AI-generated business intelligence tailored by domain.
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg font-medium shadow-sm transition-colors text-sm disabled:opacity-50"
        >
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {isLoading ? 'Generating...' : 'Regenerate All'}
        </button>
      </div>

      <div className="flex space-x-2 overflow-x-auto pb-2 border-b border-slate-200 dark:border-slate-800 hide-scrollbar mb-4">
        {MAIN_TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveMainTab(tab)}
            className={`flex items-center gap-2 px-5 py-2.5 whitespace-nowrap font-semibold text-sm rounded-t-xl transition-all ${
              activeMainTab === tab
                ? 'bg-blue-50 dark:bg-slate-800/80 text-blue-700 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800/50'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {hasAnyData && (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          
          {/* Inner Category Tabs */}
          <div className="flex space-x-2 overflow-x-auto pb-2 hide-scrollbar">
            {CATEGORIES.map(cat => {
              const hasData = !!currentTabsData[cat];
              const isGeneratingThisTab = isLoading && !hasData;
              return (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={`flex items-center gap-2 px-4 py-2 whitespace-nowrap text-sm rounded-full transition-all border ${
                    activeCategory === cat
                      ? 'bg-indigo-50 dark:bg-indigo-900/30 border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-400 font-medium shadow-sm'
                      : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'
                  }`}
                >
                  {cat}
                  {isGeneratingThisTab && <Loader2 className="w-3 h-3 animate-spin text-indigo-500" />}
                  {hasData && !isGeneratingThisTab && <div className="w-2 h-2 rounded-full bg-emerald-500" />}
                </button>
              );
            })}
          </div>

          {currentCategoryData ? (
            <div>
              {/* KPIs Section */}
              {activeMainTab === 'KPIs' && (
                <section>
                  <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-6 flex items-center gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
                    <Target className="w-6 h-6 text-blue-500" />
                    Key Performance Indicators (KPIs) - {activeCategory}
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {currentCategoryData.kpis?.map((kpi, idx) => (
                      <div key={idx} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow flex flex-col">
                        <div className="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wider mb-2">
                          {kpi.category}
                        </div>
                        <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100 mb-3">{kpi.name}</h3>
                        <p className="text-sm text-slate-600 dark:text-slate-400 mb-4 flex-1">{kpi.description}</p>
                        
                        <div className="mt-auto">
                          <div className="bg-slate-50 dark:bg-slate-950 rounded-lg p-3 border border-slate-100 dark:border-slate-800 mb-3">
                            <div className="text-xs text-slate-500 dark:text-slate-500 mb-1 flex items-center gap-1">
                              <Database className="w-3 h-3" /> Potential Value
                            </div>
                            <div className="text-sm font-medium text-slate-700 dark:text-slate-300">{kpi.potential_value}</div>
                          </div>
                          {kpi.sql_query && (
                            <div className="bg-slate-900 dark:bg-black rounded-lg p-3">
                              <div className="text-xs text-slate-400 mb-1">SQL Query Example:</div>
                              <code className="text-xs text-green-400 font-mono break-words">{kpi.sql_query}</code>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Insights Section */}
              {activeMainTab === 'Data-Driven Insights' && (
                <section>
                  <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-6 flex items-center gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
                    <Lightbulb className="w-6 h-6 text-yellow-500" />
                    Data-Driven Insights - {activeCategory}
                  </h2>
                  <div className="space-y-4">
                    {currentCategoryData.insights?.map((insight, idx) => (
                      <div key={idx} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm flex flex-col md:flex-row gap-6">
                        <div className="flex-1">
                          <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100 mb-2">{insight.finding}</h3>
                          <p className="text-slate-600 dark:text-slate-400">{insight.supporting_evidence}</p>
                        </div>
                        <div className="md:w-64 shrink-0 flex flex-col justify-center space-y-3 pl-0 md:pl-6 border-t md:border-t-0 md:border-l border-slate-200 dark:border-slate-800 pt-4 md:pt-0">
                          <div>
                            <div className="text-xs text-slate-500 mb-1">Impact</div>
                            <div className="text-sm font-medium text-slate-700 dark:text-slate-300">{insight.impact}</div>
                          </div>
                          <div>
                            <div className="text-xs text-slate-500 mb-1">Confidence Score</div>
                            <div className="w-full bg-slate-200 dark:bg-slate-800 rounded-full h-2">
                              <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${Math.max(10, (insight.confidence || 0) * 100)}%` }}></div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Opportunities Section */}
              {activeMainTab === 'Operational Opportunities' && (
                <section>
                  <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-6 flex items-center gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
                    <TrendingUp className="w-6 h-6 text-emerald-500" />
                    Operational Opportunities - {activeCategory}
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {currentCategoryData.opportunities?.map((opp, idx) => (
                      <div key={idx} className="bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/50 rounded-xl p-6 shadow-sm">
                        <div className="flex items-center gap-3 mb-3">
                          <span className="px-3 py-1 bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-400 text-xs font-bold rounded-full">
                            {opp.area}
                          </span>
                        </div>
                        <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100 mb-2">{opp.description}</h3>
                        
                        <div className="space-y-4 mt-6">
                          <div>
                            <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Potential Value</div>
                            <p className="text-sm text-slate-700 dark:text-slate-300">{opp.potential_value}</p>
                          </div>
                          <div>
                            <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Effort / Complexity</div>
                            <p className="text-sm text-slate-700 dark:text-slate-300">{opp.effort}</p>
                          </div>
                          <div className="bg-white dark:bg-slate-900 p-4 rounded-lg border border-emerald-100 dark:border-emerald-800/30">
                            <div className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase mb-2">Suggested Approach</div>
                            <p className="text-sm text-slate-600 dark:text-slate-400">{opp.suggested_approach}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Art of the Possible Section */}
              {activeMainTab === 'Art of the Possible' && (
                <section>
                  <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-6 flex items-center gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
                    <Rocket className="w-6 h-6 text-purple-500" />
                    Art of the Possible - {activeCategory}
                  </h2>
                  <div className="space-y-6">
                    {currentCategoryData.art_of_the_possible?.map((art, idx) => (
                      <div key={idx} className="bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-950/30 dark:to-purple-950/30 border border-purple-100 dark:border-purple-900/30 rounded-xl p-8 shadow-sm">
                        <h3 className="text-2xl font-bold text-indigo-900 dark:text-indigo-300 mb-4">{art.title}</h3>
                        <p className="text-indigo-800/80 dark:text-indigo-200/80 mb-6 text-lg">{art.description}</p>
                        
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div className="bg-white/60 dark:bg-slate-900/60 rounded-lg p-4">
                            <div className="text-xs font-bold text-purple-600 dark:text-purple-400 uppercase mb-1">Technologies</div>
                            <div className="text-sm text-slate-700 dark:text-slate-300">{art.technologies_needed}</div>
                          </div>
                          <div className="bg-white/60 dark:bg-slate-900/60 rounded-lg p-4">
                            <div className="text-xs font-bold text-purple-600 dark:text-purple-400 uppercase mb-1">Complexity</div>
                            <div className="text-sm text-slate-700 dark:text-slate-300">{art.complexity}</div>
                          </div>
                          <div className="bg-white/60 dark:bg-slate-900/60 rounded-lg p-4">
                            <div className="text-xs font-bold text-purple-600 dark:text-purple-400 uppercase mb-1">Business Value</div>
                            <div className="text-sm text-slate-700 dark:text-slate-300">{art.business_value}</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <Loader2 className="w-8 h-8 text-indigo-400 animate-spin mx-auto mb-4" />
              <p className="text-slate-500 dark:text-slate-400">Waiting for {activeCategory} insights...</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
