import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { extractAndSaveDb, extractFromSql, fetchConnectionDetails } from '../services/api';
import { useAppStore } from '../store/useAppStore';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Database, FileCode, Loader2, UploadCloud, CheckCircle2, Grid, ChevronRight } from 'lucide-react';
import { DATABASE_LIST } from '../config/databases';
import type { DatabaseConfig } from '../config/databases';
import { DatabaseSelectorModal } from '../components/DatabaseSelectorModal';

export const ConnectionView = () => {
  const navigate = useNavigate();
  const setMetadata = useAppStore((s) => s.setMetadata);
  const loading = useAppStore((s) => s.loading);
  const setLoading = useAppStore((s) => s.setLoading);
  const error = useAppStore((s) => s.connectionError);
  const setError = useAppStore((s) => s.setConnectionError);
  const successMessage = useAppStore((s) => s.successMessage);
  const setSuccessMessage = useAppStore((s) => s.setSuccessMessage);
  const dbType = useAppStore((s) => s.dbType);
  const setDbType = useAppStore((s) => s.setDbType);
  const host = useAppStore((s) => s.host);
  const setHost = useAppStore((s) => s.setHost);
  const port = useAppStore((s) => s.port);
  const setPort = useAppStore((s) => s.setPort);
  const database = useAppStore((s) => s.database);
  const setDatabase = useAppStore((s) => s.setDatabase);
  const username = useAppStore((s) => s.username);
  const setUsername = useAppStore((s) => s.setUsername);
  const password = useAppStore((s) => s.password);
  const setPassword = useAppStore((s) => s.setPassword);
  const validationErrors = useAppStore((s) => s.validationErrors);
  const setValidationErrors = useAppStore((s) => s.setValidationErrors);
  const sqlDbType = useAppStore((s) => s.sqlDbType);
  const setSqlDbType = useAppStore((s) => s.setSqlDbType);
  const sqlSchema = useAppStore((s) => s.sqlSchema);
  const setSqlSchema = useAppStore((s) => s.setSqlSchema);
  const sqlDbName = useAppStore((s) => s.sqlDbName);
  const setSqlDbName = useAppStore((s) => s.setSqlDbName);
  const sqlFile = useAppStore((s) => s.sqlFile);
  const setSqlFile = useAppStore((s) => s.setSqlFile);

  const [isModalOpen, setIsModalOpen] = useState(false);

  const defaultDatabases = [
    'postgres',
    'mysql',
    'sqlserver',
    'oracle',
    'mariadb',
    'sqlite',
    'sql'
  ].map(id => DATABASE_LIST.find(db => db.id === id)).filter(Boolean) as DatabaseConfig[];

  const validateForm = () => {
    const errors: { [key: string]: string } = {};
    if (!host.trim()) errors.host = 'Host is required';
    if (!port.trim()) errors.port = 'Port is required';
    if (!database.trim()) errors.database = 'Database name is required';
    if (!username.trim()) errors.username = 'Username is required';
    if (!password.trim()) errors.password = 'Password is required';

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const getFriendlyErrorMessage = (rawError: string) => {
    const lowerError = rawError.toLowerCase();
    if (lowerError.includes('password authentication failed') || lowerError.includes('authentication failed')) {
      return 'Authentication failed. Check your username or password.';
    }
    if ((lowerError.includes('does not exist') || lowerError.includes('unknown database')) && lowerError.includes('database')) {
      return 'Database not found. Verify the database name.';
    }
    if (lowerError.includes('connection refused') || lowerError.includes('could not connect to server') || lowerError.includes('unable to connect') || lowerError.includes('failed to connect')) {
      return 'Unable to connect to the database server. Check the host and port.';
    }
    return 'Connection failed. Please verify your database credentials.';
  };

  const handleDbSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;

    if (!validateForm()) {
      return;
    }

    setLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const savedConnection = await extractAndSaveDb(
        selectedDbConfig?.name || 'Database Connection', 
        '', 
        dbType, 
        { host, port, database, username, password },
        true 
      );
      
      useAppStore.getState().setCurrentConnectionId(savedConnection.id);
      setSuccessMessage("Metadata extracted and connection saved successfully!");
      
      try {
        const details = await fetchConnectionDetails(savedConnection.id);
        if (details.enriched_schema) setMetadata(details.enriched_schema);
        if (details.insights) {
          const setInsightsData = useAppStore.getState().setInsightsData;
          setInsightsData(details.insights);
        }
      } catch (detailsErr) {
        console.error("Failed to preload connection details:", detailsErr);
      }

      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (err: any) {
      console.error("Backend Error:", err);
      setError(getFriendlyErrorMessage(err.message || String(err)));
    } finally {
      setLoading(false);
    }
  };

  const handleSqlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;

    if (!sqlFile) {
      setError("Please select a .sql file.");
      return;
    }
    setLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const text = await sqlFile.text();
      const data = await extractFromSql(text, sqlDbType, sqlSchema);
      if (sqlDbName) {
        data.data.database_name = sqlDbName;
      }
      setMetadata(data.data);
      setSuccessMessage("Metadata extracted successfully.");
      setTimeout(() => {
        navigate('/schema', { state: { metadata: data.data } });
      }, 1500);
    } catch (err: any) {
      console.error("Backend Error:", err);
      setError(getFriendlyErrorMessage(err.message || String(err)));
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDatabase = (db: DatabaseConfig) => {
    setDbType(db.id as any);
    if (db.defaultPort) {
      setPort(db.defaultPort);
    }
  };

  const selectedDbConfig = DATABASE_LIST.find(db => db.id === dbType) || DATABASE_LIST[0];

  return (
    <div className="h-full flex flex-col items-center justify-start pt-6 p-4 relative overflow-hidden bg-transparent text-slate-900 dark:text-slate-50 w-full">
      <div className="w-full max-w-4xl relative z-10 flex flex-col h-full">
        <div className="text-center mb-4 flex flex-col items-center justify-center shrink-0">
          <img src="/logo1-removebg-preview.png" alt="HALO AI AGENT SOFTWARE" className="h-24 md:h-32 w-full max-w-xl object-contain mx-auto drop-shadow-[0_0_15px_rgba(0,229,255,0.4)]" />
          <p className="text-slate-600 dark:text-cyan-100/70 text-sm md:text-base max-w-md mx-auto leading-relaxed -mt-4">
            Connect to your database or upload a DDL script to instantly extract schema intelligence.
          </p>
        </div>

        {/* Database Selection Grid */}
        <div className="mb-4 w-full shrink-0">
          <h3 className="text-lg font-semibold text-slate-800 dark:text-cyan-50 mb-4 px-2">Select Source Type</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
            {defaultDatabases.map((db) => (
              <button
                key={db.id}
                onClick={() => handleSelectDatabase(db)}
                disabled={loading}
                className={`relative flex flex-col items-center justify-center p-3 rounded-2xl border transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed group
                  ${dbType === db.id 
                    ? 'bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border-cyan-500 shadow-[0_0_20px_rgba(0,229,255,0.2)] dark:bg-[#081120]' 
                    : 'bg-white/80 dark:bg-[#081120]/80 backdrop-blur-xl border-slate-200/60 dark:border-cyan-900/30 hover:border-cyan-400/50 hover:shadow-[0_0_15px_rgba(0,229,255,0.1)]'
                  }`}
              >
                {dbType === db.id && (
                  <div className="absolute top-2 right-2 bg-cyan-500 rounded-full p-0.5 shadow-[0_0_10px_rgba(0,229,255,0.5)]">
                    <CheckCircle2 className="w-3.5 h-3.5 text-white" />
                  </div>
                )}
                <div className={`mb-2 transition-transform duration-300 ${dbType !== db.id && 'group-hover:scale-110 grayscale group-hover:grayscale-0'} ${dbType === db.id ? 'scale-110' : ''}`}>
                  <div className="transform scale-75">{db.icon}</div>
                </div>
                <span className={`text-sm font-semibold text-center ${dbType === db.id ? 'text-cyan-600 dark:text-cyan-400' : 'text-slate-600 dark:text-slate-300'}`}>
                  {db.name}
                </span>
              </button>
            ))}

            {/* More Databases Card */}
            <button
              onClick={() => setIsModalOpen(true)}
              disabled={loading}
              className="flex flex-col items-center justify-center p-3 rounded-2xl border border-slate-200/60 dark:border-cyan-900/30 bg-white/50 dark:bg-[#081120]/50 backdrop-blur-xl hover:bg-slate-50 dark:hover:bg-[#0F172A]/80 hover:border-cyan-400/50 transition-all duration-300 group disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="mb-2 bg-slate-100 dark:bg-slate-800 p-2 rounded-full text-slate-500 dark:text-slate-400 group-hover:bg-cyan-100 dark:group-hover:bg-cyan-900/50 group-hover:text-cyan-600 dark:group-hover:text-cyan-400 transition-colors">
                <Grid className="w-4 h-4" />
              </div>
              <span className="text-sm font-semibold text-slate-600 dark:text-slate-300 group-hover:text-cyan-600 dark:group-hover:text-cyan-400 flex items-center gap-1">
                More <ChevronRight className="w-4 h-4" />
              </span>
            </button>
          </div>
        </div>

        {/* Dynamic Connection Form */}
        <div className="w-full mx-auto max-w-2xl flex-1 overflow-auto hide-scrollbar pb-4">
          {selectedDbConfig?.isSqlUpload ? (
            <Card className="border-slate-200/60 dark:border-cyan-900/30 bg-white/80 dark:bg-[#0F172A]/80 backdrop-blur-xl shadow-[0_0_15px_rgba(0,229,255,0.05)] rounded-3xl overflow-hidden w-full relative">
              <div className="absolute inset-0 z-0 bg-gradient-to-br from-blue-500/5 to-cyan-500/5 pointer-events-none" />
              <CardHeader className="bg-slate-50/70 dark:bg-[#081120]/70 border-b border-slate-100 dark:border-cyan-900/30 pb-3 px-6 md:px-8 relative z-10 flex flex-row items-center gap-4">
                <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded-xl">
                  {selectedDbConfig.icon}
                </div>
                <div>
                  <CardTitle className="text-xl text-slate-800 dark:text-cyan-50">SQL File Upload</CardTitle>
                  <CardDescription className="text-sm text-slate-500 dark:text-cyan-100/50">Upload a DDL script to extract metadata without a live connection.</CardDescription>
                </div>
              </CardHeader>
              <CardContent className="pt-4 px-6 md:px-8 pb-4 relative z-10">
                <form onSubmit={handleSqlSubmit} className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-5">
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">Target Database Dialect</label>
                      <select
                        className="flex h-10 w-full rounded-md border border-slate-200 dark:border-slate-700 dark:focus-visible:ring-cyan-500 bg-white dark:bg-[#081120] px-3 py-1 text-sm text-slate-900 dark:text-slate-100 shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-500"
                        value={sqlDbType}
                        onChange={(e) => setSqlDbType(e.target.value)}
                      >
                        <option value="postgres">PostgreSQL</option>
                        <option value="mysql">MySQL</option>
                        <option value="sqlserver">SQL Server</option>
                      </select>
                    </div>

                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">Schema Name</label>
                      <Input
                        className="h-10 border-slate-200 dark:border-slate-700 dark:focus-visible:ring-cyan-500 bg-white dark:bg-[#081120] text-slate-900 dark:text-slate-100"
                        type="text"
                        placeholder="e.g., public"
                        value={sqlSchema}
                        onChange={(e) => setSqlSchema(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">Database Name (Optional)</label>
                    <Input
                      className="h-10 border-slate-200 dark:border-slate-700 dark:focus-visible:ring-cyan-500 bg-white dark:bg-[#081120] text-slate-900 dark:text-slate-100"
                      type="text"
                      placeholder="e.g., my_database"
                      value={sqlDbName}
                      onChange={(e) => setSqlDbName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2 pt-1">
                    <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">Upload .sql File</label>
                    <div className="border-2 border-dashed border-slate-300 dark:border-cyan-800/50 rounded-xl p-4 flex flex-col items-center justify-center text-slate-500 hover:bg-slate-50 dark:hover:bg-[#081120]/50 transition-colors cursor-pointer relative bg-white dark:bg-[#081120]">
                      <UploadCloud className="w-8 h-8 mb-2 text-cyan-500" />
                      <Input
                        type="file"
                        accept=".sql"
                        className="max-w-[200px] text-slate-900 dark:text-slate-100"
                        onChange={(e) => {
                          if (e.target.files && e.target.files.length > 0) {
                            setSqlFile(e.target.files[0]);
                            setError(null);
                          }
                        }}
                      />
                    </div>
                  </div>

                  {error && <div className="text-sm font-medium text-red-700 bg-red-50 border border-red-200 dark:bg-red-950/50 dark:border-red-900/50 dark:text-red-400 p-4 rounded-xl mt-4">{error}</div>}
                  {successMessage && <div className="text-sm font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 dark:bg-cyan-950/40 dark:border-cyan-800/50 dark:text-cyan-400 p-4 rounded-xl mt-4 flex items-center gap-2"><CheckCircle2 className="w-5 h-5" />{successMessage}</div>}

                  <Button type="submit" className="w-full mt-4 h-10 text-sm font-semibold rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white shadow-[0_0_15px_rgba(0,229,255,0.2)] transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed" disabled={loading}>
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileCode className="mr-2 h-4 w-4" />}
                    {loading ? 'Parsing SQL...' : 'Parse SQL File'}
                  </Button>
                </form>
              </CardContent>
            </Card>
          ) : (
            <Card className="border-slate-200/60 dark:border-cyan-900/30 bg-white/80 dark:bg-[#0F172A]/80 backdrop-blur-xl shadow-[0_0_15px_rgba(0,229,255,0.05)] rounded-3xl overflow-hidden w-full relative">
              <div className="absolute inset-0 z-0 bg-gradient-to-br from-blue-500/5 to-cyan-500/5 pointer-events-none" />
              <CardHeader className="bg-slate-50/70 dark:bg-[#081120]/70 border-b border-slate-100 dark:border-cyan-900/30 pb-3 px-6 md:px-8 relative z-10 flex flex-row items-center gap-4">
                <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded-xl transform scale-75">
                  {selectedDbConfig?.icon}
                </div>
                <div>
                  <CardTitle className="text-lg text-slate-800 dark:text-cyan-50">{selectedDbConfig?.name} Connection</CardTitle>
                  <CardDescription className="text-xs text-slate-500 dark:text-cyan-100/50">Enter credentials to securely extract schema metadata.</CardDescription>
                </div>
              </CardHeader>
              <CardContent className="pt-4 px-6 md:px-8 pb-4 relative z-10">
                <form onSubmit={handleDbSubmit} className="space-y-4" noValidate>
                  
                  {selectedDbConfig?.category !== 'Embedded' && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-5">
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">Host</label>
                        <Input disabled={loading} className={`h-10 border-slate-200 dark:border-slate-700 dark:focus-visible:ring-cyan-500 bg-white dark:bg-[#081120] text-slate-900 dark:text-slate-100 ${validationErrors.host ? 'border-red-500 dark:border-red-500 focus-visible:ring-red-500' : ''}`} placeholder="localhost" value={host} onChange={(e) => { setHost(e.target.value); setValidationErrors(prev => ({ ...prev, host: '' })); }} />
                        {validationErrors.host && <p className="text-xs text-red-500 mt-1">{validationErrors.host}</p>}
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">Port</label>
                        <Input disabled={loading} className={`h-10 border-slate-200 dark:border-slate-700 dark:focus-visible:ring-cyan-500 bg-white dark:bg-[#081120] text-slate-900 dark:text-slate-100 ${validationErrors.port ? 'border-red-500 dark:border-red-500 focus-visible:ring-red-500' : ''}`} placeholder={selectedDbConfig?.defaultPort || "5432"} value={port} onChange={(e) => { setPort(e.target.value); setValidationErrors(prev => ({ ...prev, port: '' })); }} />
                        {validationErrors.port && <p className="text-xs text-red-500 mt-1">{validationErrors.port}</p>}
                      </div>
                    </div>
                  )}
                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">
                      {selectedDbConfig?.id === 'sqlite' ? 'Database File Path' : 'Database Name'}
                    </label>
                    <Input disabled={loading} className={`h-10 border-slate-200 dark:border-slate-700 dark:focus-visible:ring-cyan-500 bg-white dark:bg-[#081120] text-slate-900 dark:text-slate-100 ${validationErrors.database ? 'border-red-500 dark:border-red-500 focus-visible:ring-red-500' : ''}`} placeholder={selectedDbConfig?.id === 'sqlite' ? "/path/to/database.db" : "db_name"} value={database} onChange={(e) => { setDatabase(e.target.value); setValidationErrors(prev => ({ ...prev, database: '' })); }} />
                    {validationErrors.database && <p className="text-xs text-red-500 mt-1">{validationErrors.database}</p>}
                  </div>
                  
                  {selectedDbConfig?.category !== 'Embedded' && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-5">
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">Username</label>
                        <Input disabled={loading} className={`h-10 border-slate-200 dark:border-slate-700 dark:focus-visible:ring-cyan-500 bg-white dark:bg-[#081120] text-slate-900 dark:text-slate-100 ${validationErrors.username ? 'border-red-500 dark:border-red-500 focus-visible:ring-red-500' : ''}`} placeholder="admin" value={username} onChange={(e) => { setUsername(e.target.value); setValidationErrors(prev => ({ ...prev, username: '' })); }} />
                        {validationErrors.username && <p className="text-xs text-red-500 mt-1">{validationErrors.username}</p>}
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">Password</label>
                        <Input disabled={loading} className={`h-10 border-slate-200 dark:border-slate-700 dark:focus-visible:ring-cyan-500 bg-white dark:bg-[#081120] text-slate-900 dark:text-slate-100 ${validationErrors.password ? 'border-red-500 dark:border-red-500 focus-visible:ring-red-500' : ''}`} type="password" placeholder="••••••••" value={password} onChange={(e) => { setPassword(e.target.value); setValidationErrors(prev => ({ ...prev, password: '' })); }} />
                        {validationErrors.password && <p className="text-xs text-red-500 mt-1">{validationErrors.password}</p>}
                      </div>
                    </div>
                  )}

                  {error && <div className="text-sm font-medium text-red-700 bg-red-50 border border-red-200 dark:bg-red-950/50 dark:border-red-900/50 dark:text-red-400 p-4 rounded-xl mt-4">{error}</div>}
                  {successMessage && <div className="text-sm font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 dark:bg-cyan-950/40 dark:border-cyan-800/50 dark:text-cyan-400 p-4 rounded-xl mt-4 flex items-center gap-2"><CheckCircle2 className="w-5 h-5" />{successMessage}</div>}

                  <Button type="submit" className="w-full mt-4 h-10 text-sm font-semibold rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white shadow-[0_0_15px_rgba(0,229,255,0.2)] transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed" disabled={loading}>
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Database className="mr-2 h-4 w-4" />}
                    {loading ? 'Extracting Metadata...' : 'Extract Metadata'}
                  </Button>
                </form>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <DatabaseSelectorModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSelect={handleSelectDatabase}
      />
    </div>
  );
};
