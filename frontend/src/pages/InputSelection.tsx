import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { extractFromDb, extractFromSql } from '../services/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Database, FileCode, Loader2, UploadCloud } from 'lucide-react';

export const InputSelection = () => {
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
  const [sqlFile, setSqlFile] = useState<File | null>(null);

  const handleDbSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await extractFromDb(dbType, { host, port, database, username, password });
      navigate('/dashboard', { state: { metadata: data.data } });
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
      const data = await extractFromSql(text, sqlDbType, sqlSchema);
      navigate('/dashboard', { state: { metadata: data.data } });
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent mb-2">
            ETL Metadata Platform
          </h1>
          <p className="text-slate-500 dark:text-slate-400">Extract schema intelligence instantly.</p>
        </div>

        <Tabs defaultValue="db" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-6">
            <TabsTrigger value="db" className="flex items-center gap-2">
              <Database className="w-4 h-4" /> Credentials
            </TabsTrigger>
            <TabsTrigger value="sql" className="flex items-center gap-2">
              <FileCode className="w-4 h-4" /> SQL Upload
            </TabsTrigger>
          </TabsList>

          <TabsContent value="db">
            <Card className="border-slate-200 dark:border-slate-800 shadow-xl shadow-slate-200/50 dark:shadow-none">
              <CardHeader>
                <CardTitle>Database Connection</CardTitle>
                <CardDescription>Connect directly to extract live schema metadata.</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleDbSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Database Type</label>
                    <select
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                      value={dbType}
                      onChange={(e) => setDbType(e.target.value)}
                    >
                      <option value="postgres">PostgreSQL</option>
                      <option value="mysql">MySQL</option>
                      <option value="mariadb">MariaDB</option>
                      <option value="sqlserver">SQL Server</option>
                      <option value="oracle">Oracle</option>
                      <option value="sqlite">SQLite</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Host</label>
                      <Input placeholder="localhost" value={host} onChange={(e) => setHost(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Port</label>
                      <Input placeholder="5432" value={port} onChange={(e) => setPort(e.target.value)} />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Database Name</label>
                    <Input placeholder="db_name" value={database} onChange={(e) => setDatabase(e.target.value)} />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Username</label>
                      <Input placeholder="admin" value={username} onChange={(e) => setUsername(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Password</label>
                      <Input type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} />
                    </div>
                  </div>

                  {error && <div className="text-sm text-red-500 bg-red-50 dark:bg-red-950/50 p-3 rounded-md">{error}</div>}

                  <Button type="submit" className="w-full mt-2" disabled={loading}>
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Database className="mr-2 h-4 w-4" />}
                    {loading ? 'Extracting...' : 'Extract Metadata'}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="sql">
            <Card className="border-slate-200 dark:border-slate-800 shadow-xl shadow-slate-200/50 dark:shadow-none">
              <CardHeader>
                <CardTitle>SQL File Upload</CardTitle>
                <CardDescription>Upload a DDL script containing CREATE TABLE statements.</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSqlSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Target Database Dialect</label>
                    <select
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                      value={sqlDbType}
                      onChange={(e) => setSqlDbType(e.target.value)}
                    >
                      <option value="postgres">PostgreSQL</option>
                      <option value="mysql">MySQL</option>
                      <option value="sqlserver">SQL Server</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Database / Schema Name</label>
                    <Input placeholder="public" value={sqlSchema} onChange={(e) => setSqlSchema(e.target.value)} />
                  </div>
                  
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Upload .sql File</label>
                    <div className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-lg p-8 flex flex-col items-center justify-center text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors">
                      <UploadCloud className="w-8 h-8 mb-3 text-slate-400" />
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

                  {error && <div className="text-sm text-red-500 bg-red-50 dark:bg-red-950/50 p-3 rounded-md">{error}</div>}

                  <Button type="submit" className="w-full mt-2" disabled={loading}>
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileCode className="mr-2 h-4 w-4" />}
                    {loading ? 'Parsing...' : 'Parse SQL'}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};
