import React from 'react';
import { useNavigate } from 'react-router-dom';
import { extractFromDb, extractFromSql } from '../services/api';
import { useAppStore } from '../store/useAppStore';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Database, FileCode, Loader2, UploadCloud, CheckCircle2 } from 'lucide-react';

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
      const data = await extractFromDb(dbType, { host, port, database, username, password });
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

  return (
    <div className="h-full flex flex-col items-center justify-start pt-12 md:justify-center md:pt-6 p-4 relative overflow-auto bg-transparent text-slate-900 dark:text-slate-50 w-full">

      <div className="w-full max-w-3xl relative z-10">
        <div className="text-center mb-8 flex flex-col items-center justify-center">
          <img src="/logo1-removebg-preview.png" alt="HALO AI AGENT SOFTWARE" className="h-48 md:h-64 w-full max-w-xl object-contain mx-auto drop-shadow-[0_0_15px_rgba(0,229,255,0.4)]" />
          <p className="text-slate-600 dark:text-cyan-100/70 text-base md:text-lg max-w-md mx-auto leading-relaxed -mt-8">
            Connect to your database or upload a DDL script to instantly extract schema intelligence.
          </p>
        </div>

        <Tabs value={dbType} onValueChange={(val) => {
          if (val === 'sql') setDbType('sql');
          else setDbType(val as any);
        }} className="w-full flex flex-col items-center">
          <TabsList className="flex w-full bg-white/80 dark:bg-[#081120]/80 backdrop-blur-xl border border-slate-200/60 dark:border-cyan-900/30 shadow-sm rounded-2xl p-1.5 mb-8 gap-1 md:gap-1.5 justify-start md:justify-center overflow-x-auto hide-scrollbar">
            {['postgres', 'mysql', 'mariadb', 'sqlserver', 'oracle', 'sqlite'].map((type) => (
              <TabsTrigger
                key={type}
                value={type}
                disabled={loading}
                className="flex-1 min-w-[70px] md:min-w-[80px] text-[11px] md:text-xs font-semibold py-2.5 px-2 rounded-xl text-slate-600 dark:text-cyan-100/70 data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-600 data-[state=active]:to-cyan-500 data-[state=active]:text-white data-[state=active]:shadow-[0_0_10px_rgba(0,229,255,0.3)] hover:bg-slate-100 dark:hover:bg-slate-800/50 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {type === 'postgres' ? 'PostgreSQL' :
                  type === 'mysql' ? 'MySQL' :
                    type === 'mariadb' ? 'MariaDB' :
                      type === 'sqlserver' ? 'SQL Server' :
                        type === 'oracle' ? 'Oracle' : 'SQLite'}
              </TabsTrigger>
            ))}
            <TabsTrigger
              value="sql"
              disabled={loading}
              className="flex-1 min-w-[70px] md:min-w-[80px] flex items-center justify-center gap-1.5 text-[11px] md:text-xs font-semibold py-2.5 px-2 rounded-xl text-slate-600 dark:text-cyan-100/70 data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-600 data-[state=active]:to-cyan-500 data-[state=active]:text-white data-[state=active]:shadow-[0_0_10px_rgba(0,229,255,0.3)] hover:bg-slate-100 dark:hover:bg-slate-800/50 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <FileCode className="w-3.5 h-3.5 shrink-0" /> <span className="whitespace-nowrap">SQL Upload</span>
            </TabsTrigger>
          </TabsList>

          <div className="w-full max-w-xl mx-auto">
            {['postgres', 'mysql', 'mariadb', 'sqlserver', 'oracle', 'sqlite'].map((type) => (
              <TabsContent key={type} value={type} className="focus-visible:outline-none w-full m-0">
                <Card className="border-slate-200/60 dark:border-cyan-900/30 bg-white/80 dark:bg-[#0F172A]/80 backdrop-blur-xl shadow-[0_0_15px_rgba(0,229,255,0.05)] rounded-3xl overflow-hidden w-full relative">
                  <div className="absolute inset-0 z-0 bg-gradient-to-br from-blue-500/5 to-cyan-500/5 pointer-events-none" />
                  <CardHeader className="bg-slate-50/70 dark:bg-[#081120]/70 border-b border-slate-100 dark:border-cyan-900/30 pb-5 px-6 md:px-8 relative z-10">
                    <CardTitle className="text-xl text-slate-800 dark:text-cyan-50">Database Connection</CardTitle>
                    <CardDescription className="text-sm text-slate-500 dark:text-cyan-100/50">Enter your credentials to securely extract schema metadata directly from the source.</CardDescription>
                  </CardHeader>
                  <CardContent className="pt-6 px-6 md:px-8 pb-8 relative z-10">
                    <form onSubmit={handleDbSubmit} className="space-y-5" noValidate>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-5">
                        <div className="space-y-2">
                          <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">Host</label>
                          <Input disabled={loading} className={`h-10 border-slate-200 dark:border-slate-700 dark:focus-visible:ring-cyan-500 bg-white dark:bg-[#081120] text-slate-900 dark:text-slate-100 ${validationErrors.host ? 'border-red-500 dark:border-red-500 focus-visible:ring-red-500' : ''}`} placeholder="localhost" value={host} onChange={(e) => { setHost(e.target.value); setValidationErrors(prev => ({ ...prev, host: '' })); }} />
                          {validationErrors.host && <p className="text-xs text-red-500 mt-1">{validationErrors.host}</p>}
                        </div>
                        <div className="space-y-2">
                          <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">Port</label>
                          <Input disabled={loading} className={`h-10 border-slate-200 dark:border-slate-700 dark:focus-visible:ring-cyan-500 bg-white dark:bg-[#081120] text-slate-900 dark:text-slate-100 ${validationErrors.port ? 'border-red-500 dark:border-red-500 focus-visible:ring-red-500' : ''}`} placeholder="5432" value={port} onChange={(e) => { setPort(e.target.value); setValidationErrors(prev => ({ ...prev, port: '' })); }} />
                          {validationErrors.port && <p className="text-xs text-red-500 mt-1">{validationErrors.port}</p>}
                        </div>
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">Database Name</label>
                        <Input disabled={loading} className={`h-10 border-slate-200 dark:border-slate-700 dark:focus-visible:ring-cyan-500 bg-white dark:bg-[#081120] text-slate-900 dark:text-slate-100 ${validationErrors.database ? 'border-red-500 dark:border-red-500 focus-visible:ring-red-500' : ''}`} placeholder="db_name" value={database} onChange={(e) => { setDatabase(e.target.value); setValidationErrors(prev => ({ ...prev, database: '' })); }} />
                        {validationErrors.database && <p className="text-xs text-red-500 mt-1">{validationErrors.database}</p>}
                      </div>
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

                      {error && <div className="text-sm font-medium text-red-700 bg-red-50 border border-red-200 dark:bg-red-950/50 dark:border-red-900/50 dark:text-red-400 p-4 rounded-xl mt-4">{error}</div>}
                      {successMessage && <div className="text-sm font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 dark:bg-cyan-950/40 dark:border-cyan-800/50 dark:text-cyan-400 p-4 rounded-xl mt-4 flex items-center gap-2"><CheckCircle2 className="w-5 h-5" />{successMessage}</div>}

                      <Button type="submit" className="w-full mt-6 h-12 text-base font-semibold rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white shadow-[0_0_15px_rgba(0,229,255,0.2)] transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed" disabled={loading}>
                        {loading ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <Database className="mr-2 h-5 w-5" />}
                        {loading ? 'Extracting Metadata...' : 'Extract Metadata'}
                      </Button>
                    </form>
                  </CardContent>
                </Card>
              </TabsContent>
            ))}

            <TabsContent value="sql" className="focus-visible:outline-none w-full m-0">
              <Card className="border-slate-200/60 dark:border-cyan-900/30 bg-white/80 dark:bg-[#0F172A]/80 backdrop-blur-xl shadow-[0_0_15px_rgba(0,229,255,0.05)] rounded-3xl overflow-hidden w-full relative">
                <div className="absolute inset-0 z-0 bg-gradient-to-br from-blue-500/5 to-cyan-500/5 pointer-events-none" />
                <CardHeader className="bg-slate-50/70 dark:bg-[#081120]/70 border-b border-slate-100 dark:border-cyan-900/30 pb-5 px-6 md:px-8 relative z-10">
                  <CardTitle className="text-xl text-slate-800 dark:text-cyan-50">SQL File Upload</CardTitle>
                  <CardDescription className="text-sm text-slate-500 dark:text-cyan-100/50">Upload a DDL script (e.g. `schema.sql`) to parse and extract metadata without a live connection.</CardDescription>
                </CardHeader>
                <CardContent className="pt-6 px-6 md:px-8 pb-8 relative z-10">
                  <form onSubmit={handleSqlSubmit} className="space-y-5">
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
                    <div className="space-y-3 pt-2">
                      <label className="text-sm font-semibold text-slate-700 dark:text-cyan-100">Upload .sql File</label>
                      <div className="border-2 border-dashed border-slate-300 dark:border-cyan-800/50 rounded-2xl p-8 flex flex-col items-center justify-center text-slate-500 hover:bg-slate-50 dark:hover:bg-[#081120]/50 transition-colors cursor-pointer relative bg-white dark:bg-[#081120]">
                        <UploadCloud className="w-10 h-10 mb-3 text-cyan-500" />
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

                    <Button type="submit" className="w-full mt-6 h-12 text-base font-semibold rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white shadow-[0_0_15px_rgba(0,229,255,0.2)] transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed" disabled={loading}>
                      {loading ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <FileCode className="mr-2 h-5 w-5" />}
                      {loading ? 'Parsing SQL...' : 'Parse SQL File'}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </div>
  );
};

