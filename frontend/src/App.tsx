
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MainLayout } from './components/layout/MainLayout';
import { ConnectionView } from './pages/ConnectionView';
import { SchemaView } from './pages/SchemaView';
import { InsightsView } from './pages/InsightsView';
import { SqlAgentView } from './pages/SqlAgentView';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Navigate to="/connection" replace />} />
            <Route path="connection" element={<ConnectionView />} />
            <Route path="schema" element={<SchemaView />} />
            <Route path="insights" element={<InsightsView />} />
            <Route path="sql-agent" element={<SqlAgentView />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
