export const extractFromDb = async (dbType: string, creds: any) => {
  const response = await fetch('/extract', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ database_type: dbType, credentials: creds }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Failed to extract from DB');
  return data;
};

export const extractAndSaveDb = async (name: string, description: string, dbType: string, creds: any, generateInsights: boolean = true) => {
  const response = await fetch('/connections/extract-and-save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      name, 
      description, 
      database_type: dbType, 
      credentials: creds,
      generate_insights: generateInsights
    }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Failed to extract and save connection');
  return data;
};

export const extractFromSql = async (sqlText: string, dbType: string, schema: string = 'public') => {
  const response = await fetch('/parse-sql', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sql_text: sqlText, database_type: dbType, schema }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Failed to parse SQL');
  return data;
};

export const fetchEmbeddingStatus = async () => {
  const response = await fetch('/embedding/status');
  if (!response.ok) throw new Error('Failed to fetch embedding status');
  return response.json();
};

export const generateInsights = async (domain?: string, entity?: string) => {
  const response = await fetch('/api/v1/insights/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ domain: domain || null, entity: entity || null }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Failed to generate insights');
  return data;
};

export const fetchSavedConnections = async () => {
  const response = await fetch('/connections');
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Failed to fetch saved connections');
  return data;
};

export const fetchConnectionDetails = async (connectionId: string) => {
  const response = await fetch(`/connections/${connectionId}/details`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Failed to fetch connection details');
  return data;
};

export const regenerateCategoryInsights = async (connectionId: string, category: string) => {
  const response = await fetch(`/connections/${connectionId}/regenerate-insights/${encodeURIComponent(category)}`, {
    method: 'POST',
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Failed to regenerate category insights');
  return data;
};
