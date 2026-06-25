import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { extractFromDb, extractFromSql } from '../services/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Database, FileCode, Loader2, UploadCloud } from 'lucide-react';

export const ConnectionView = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // DB State
  const [dbType, setDbType] = useState('postgres');
  const [host, setHost] = useState('localhost');
  const [port, setPort] = useState('5432');
  const [database, setDatabase] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // SQL State
  const [sqlDbType, setSqlDbType] = useState('postgres');
  const [sqlSchema, setSqlSchema] = useState('public');
  const [sqlDbName, setSqlDbName] = useState('');
  const [sqlFile, setSqlFile] = useState<File | null>(null);

  const handleDbSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await extractFromDb(dbType, { host, port, database, username, password });
      navigate('/schema', { state: { metadata: data.data } });
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSqlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sqlFile) {
      setError("Please select a .sql file.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const text = await sqlFile.text();
      const data = await extractFromSql(text, sqlDbType, sqlSchema); // sqlDbName can be appended here if backend accepts it in future
      if (sqlDbName) {
        data.data.database_name = sqlDbName;
      }
      navigate('/schema', { state: { metadata: data.data } });
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col items-center justify-start pt-12 md:justify-center md:pt-6 p-4 relative overflow-auto bg-slate-50 dark:bg-slate-950">
      {/* Decorative Background */}
      <div className="absolute inset-0 z-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-100/50 via-slate-50/20 to-slate-50 dark:from-blue-900/20 dark:via-slate-950/20 dark:to-slate-950 pointer-events-none" />

      <div className="w-full max-w-xl relative z-10">
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center p-3.5 bg-blue-100 dark:bg-blue-900/40 rounded-2xl mb-5 shadow-sm">
            <Database className="w-7 h-7 text-blue-600 dark:text-blue-400" />
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent mb-4">
            HALO
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-base md:text-lg max-w-md mx-auto leading-relaxed">
            Connect to your database or upload a DDL script to instantly extract schema intelligence.
          </p>
        </div>

        <Tabs value={dbType} onValueChange={(val) => {
          if (val === 'sql') setDbType('sql');
          else setDbType(val);
        }} className="w-full flex flex-col items-center">
          <TabsList className="flex flex-wrap w-full bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border border-slate-200/60 dark:border-slate-800/60 shadow-sm rounded-2xl p-1.5 mb-8 gap-1 md:gap-1.5 justify-center overflow-x-auto overflow-y-hidden">
            {['postgres', 'mysql', 'mariadb', 'sqlserver', 'oracle', 'sqlite'].map((type) => (
              <TabsTrigger
                key={type}
                value={type}
                className="flex-1 min-w-[70px] md:min-w-[80px] text-[11px] md:text-xs font-semibold py-2.5 px-2 rounded-xl data-[state=active]:bg-blue-600 data-[state=active]:text-white data-[state=active]:shadow-md data-[state=active]:shadow-blue-600/20 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all duration-300"
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
              className="flex-1 min-w-[90px] md:min-w-[100px] flex items-center justify-center gap-1.5 text-[11px] md:text-xs font-bold py-2.5 px-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 data-[state=active]:bg-indigo-600 data-[state=active]:text-white data-[state=active]:shadow-md data-[state=active]:shadow-indigo-600/20 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all duration-300"
            >
              <FileCode className="w-3.5 h-3.5 shrink-0" /> <span className="whitespace-nowrap">SQL Upload</span>
            </TabsTrigger>
          </TabsList>

          <div className="w-full">

            {['postgres', 'mysql', 'mariadb', 'sqlserver', 'oracle', 'sqlite'].map((type) => (
              <TabsContent key={type} value={type} className="focus-visible:outline-none w-full m-0">
                <Card className="border-slate-200/60 dark:border-slate-800/60 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl shadow-xl shadow-blue-500/5 dark:shadow-none rounded-3xl overflow-hidden w-full">
                  <CardHeader className="bg-slate-50/70 dark:bg-slate-900/70 border-b border-slate-100 dark:border-slate-800/60 pb-5 px-6 md:px-8">
                    <CardTitle className="text-xl text-slate-800 dark:text-slate-100">Database Connection</CardTitle>
                    <CardDescription className="text-sm">Enter your credentials to securely extract schema metadata directly from the source.</CardDescription>
                  </CardHeader>
                  <CardContent className="pt-6 px-6 md:px-8 pb-8">
                    <form onSubmit={handleDbSubmit} className="space-y-5">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-5">
                        <div className="space-y-2">
                          <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Host</label>
                          <Input className="h-10 border-slate-200 dark:border-slate-700" placeholder="localhost" value={host} onChange={(e) => setHost(e.target.value)} />
                        </div>
                        <div className="space-y-2">
                          <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Port</label>
                          <Input className="h-10 border-slate-200 dark:border-slate-700" placeholder="5432" value={port} onChange={(e) => setPort(e.target.value)} />
                        </div>
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Database Name</label>
                        <Input className="h-10 border-slate-200 dark:border-slate-700" placeholder="db_name" value={database} onChange={(e) => setDatabase(e.target.value)} />
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-5">
                        <div className="space-y-2">
                          <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Username</label>
                          <Input className="h-10 border-slate-200 dark:border-slate-700" placeholder="admin" value={username} onChange={(e) => setUsername(e.target.value)} />
                        </div>
                        <div className="space-y-2">
                          <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Password</label>
                          <Input className="h-10 border-slate-200 dark:border-slate-700" type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} />
                        </div>
                      </div>

                      {error && <div className="text-sm font-medium text-red-600 bg-red-50 border border-red-100 dark:bg-red-950/40 dark:border-red-900/50 dark:text-red-400 p-4 rounded-xl mt-4">{error}</div>}

                      <Button type="submit" className="w-full mt-6 h-12 text-base font-semibold rounded-xl bg-blue-600 hover:bg-blue-700 shadow-lg shadow-blue-600/20 transition-all duration-200" disabled={loading}>
                        {loading ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <Database className="mr-2 h-5 w-5" />}
                        {loading ? 'Extracting Metadata...' : 'Extract Metadata'}
                      </Button>
                    </form>
                  </CardContent>
                </Card>
              </TabsContent>
            ))}

            <TabsContent value="sql" className="focus-visible:outline-none w-full m-0">
              <Card className="border-slate-200/60 dark:border-slate-800/60 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl shadow-xl shadow-indigo-500/5 dark:shadow-none rounded-3xl overflow-hidden w-full">
                <CardHeader className="bg-slate-50/70 dark:bg-slate-900/70 border-b border-slate-100 dark:border-slate-800/60 pb-5 px-6 md:px-8">
                  <CardTitle className="text-xl text-slate-800 dark:text-slate-100">SQL File Upload</CardTitle>
                  <CardDescription className="text-sm">Upload a DDL script (e.g. `schema.sql`) to parse and extract metadata without a live connection.</CardDescription>
                </CardHeader>
                <CardContent className="pt-6 px-6 md:px-8 pb-8">
                  <form onSubmit={handleSqlSubmit} className="space-y-5">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:gap-5">
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Target Database Dialect</label>
                        <select
                          className="flex h-10 w-full rounded-md border border-slate-200 dark:border-slate-700 bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500"
                          value={sqlDbType}
                          onChange={(e) => setSqlDbType(e.target.value)}
                        >
                          <option value="postgres">PostgreSQL</option>
                          <option value="mysql">MySQL</option>
                          <option value="sqlserver">SQL Server</option>
                        </select>
                      </div>

                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Schema Name</label>
                        <Input
                          className="h-10 border-slate-200 dark:border-slate-700"
                          type="text"
                          placeholder="e.g., public"
                          value={sqlSchema}
                          onChange={(e) => setSqlSchema(e.target.value)}
                        />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Database Name (Optional)</label>
                      <Input
                        className="h-10 border-slate-200 dark:border-slate-700"
                        type="text"
                        placeholder="e.g., my_database"
                        value={sqlDbName}
                        onChange={(e) => setSqlDbName(e.target.value)}
                      />
                    </div>
                    <div className="space-y-3 pt-2">
                      <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">Upload .sql File</label>
                      <div className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-2xl p-8 flex flex-col items-center justify-center text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer relative">
                        <UploadCloud className="w-10 h-10 mb-3 text-indigo-400" />
                        <Input
                          type="file"
                          accept=".sql"
                          className="max-w-[200px]"
                          onChange={(e) => {
                            if (e.target.files && e.target.files.length > 0) {
                              setSqlFile(e.target.files[0]);
                            }
                          }}
                        />
                      </div>
                    </div>

                    {error && <div className="text-sm font-medium text-red-600 bg-red-50 border border-red-100 dark:bg-red-950/40 dark:border-red-900/50 dark:text-red-400 p-4 rounded-xl">{error}</div>}

                    <Button type="submit" className="w-full mt-6 h-12 text-base font-semibold rounded-xl bg-indigo-600 hover:bg-indigo-700 shadow-lg shadow-indigo-600/20 transition-all duration-200" disabled={loading}>
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
