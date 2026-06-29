import { create } from 'zustand';

export type TabType = 'postgres' | 'mysql' | 'mariadb' | 'sqlserver' | 'oracle' | 'sqlite' | 'sql';

// ── Normalized types (re-exported for convenience) ──
export interface EmbeddingStatus {
  status: 'idle' | 'embedding' | 'complete' | 'failed';
  updated_at: string | null;
  error: string | null;
}

// ── App state ──
export interface AppState {
  // Layout
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (v: boolean) => void;

  // Connection — DB form
  connectionName: string;
  setConnectionName: (v: string) => void;
  connectionDescription: string;
  setConnectionDescription: (v: string) => void;
  dbType: TabType;
  setDbType: (v: TabType) => void;
  host: string;
  setHost: (v: string) => void;
  port: string;
  setPort: (v: string) => void;
  database: string;
  setDatabase: (v: string) => void;
  username: string;
  setUsername: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  validationErrors: Record<string, string>;
  setValidationErrors: (e: Record<string, string> | ((prev: Record<string, string>) => Record<string, string>)) => void;

  // Connection — SQL form
  sqlDbType: string;
  setSqlDbType: (v: string) => void;
  sqlSchema: string;
  setSqlSchema: (v: string) => void;
  sqlDbName: string;
  setSqlDbName: (v: string) => void;
  sqlFile: File | null;
  setSqlFile: (f: File | null) => void;

  // Connection — transient UI
  loading: boolean;
  setLoading: (v: boolean) => void;
  connectionError: string | null;
  setConnectionError: (e: string | null) => void;
  successMessage: string | null;
  setSuccessMessage: (m: string | null) => void;

  // Schema view — UI state
  selectedTable: Record<string, any> | null;
  setSelectedTable: (t: Record<string, any> | null) => void;
  selectedView: Record<string, any> | null;
  setSelectedView: (v: Record<string, any> | null) => void;
  isModalOpen: boolean;
  setIsModalOpen: (v: boolean) => void;
  isViewModalOpen: boolean;
  setIsViewModalOpen: (v: boolean) => void;
  schemaActiveTab: 'overview' | 'graph';
  setSchemaActiveTab: (t: 'overview' | 'graph') => void;
  tablesExpanded: boolean;
  setTablesExpanded: (v: boolean) => void;
  viewsExpanded: boolean;
  setViewsExpanded: (v: boolean) => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;

  // Insights view
  insightsData: Record<string, any> | null;
  setInsightsData: (d: Record<string, any> | null) => void;
  insightsLoading: boolean;
  setInsightsLoading: (v: boolean) => void;
  insightsError: string | null;
  setInsightsError: (e: string | null) => void;

  // Pipeline metadata (preserved across tabs)
  metadata: Record<string, any> | null;
  setMetadata: (m: Record<string, any>) => void;

  // Embedding status (polled from backend)
  embeddingStatus: EmbeddingStatus;
  setEmbeddingStatus: (s: EmbeddingStatus) => void;

  /** Reset everything */
  reset: () => void;
}

export const useAppStore = create<AppState>()((set) => ({
  // Layout
  sidebarCollapsed: false,
  setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),

  // Connection — DB form defaults
  connectionName: '',
  setConnectionName: (connectionName) => set({ connectionName }),
  connectionDescription: '',
  setConnectionDescription: (connectionDescription) => set({ connectionDescription }),
  dbType: 'postgres',
  setDbType: (dbType) => set({ dbType }),
  host: 'localhost',
  setHost: (host) => set({ host }),
  port: '5432',
  setPort: (port) => set({ port }),
  database: '',
  setDatabase: (database) => set({ database }),
  username: '',
  setUsername: (username) => set({ username }),
  password: '',
  setPassword: (password) => set({ password }),
  validationErrors: {},
  setValidationErrors: (validationErrors) =>
    set((state) => ({
      validationErrors:
        typeof validationErrors === 'function'
          ? validationErrors(state.validationErrors)
          : validationErrors,
    })),

  // Connection — SQL form defaults
  sqlDbType: 'postgres',
  setSqlDbType: (sqlDbType) => set({ sqlDbType }),
  sqlSchema: 'public',
  setSqlSchema: (sqlSchema) => set({ sqlSchema }),
  sqlDbName: '',
  setSqlDbName: (sqlDbName) => set({ sqlDbName }),
  sqlFile: null,
  setSqlFile: (sqlFile) => set({ sqlFile }),

  // Connection — transient UI
  loading: false,
  setLoading: (loading) => set({ loading }),
  connectionError: null,
  setConnectionError: (connectionError) => set({ connectionError }),
  successMessage: null,
  setSuccessMessage: (successMessage) => set({ successMessage }),

  // Schema view — UI state
  selectedTable: null,
  setSelectedTable: (selectedTable) => set({ selectedTable }),
  selectedView: null,
  setSelectedView: (selectedView) => set({ selectedView }),
  isModalOpen: false,
  setIsModalOpen: (isModalOpen) => set({ isModalOpen }),
  isViewModalOpen: false,
  setIsViewModalOpen: (isViewModalOpen) => set({ isViewModalOpen }),
  schemaActiveTab: 'overview',
  setSchemaActiveTab: (schemaActiveTab) => set({ schemaActiveTab }),
  tablesExpanded: true,
  setTablesExpanded: (tablesExpanded) => set({ tablesExpanded }),
  viewsExpanded: true,
  setViewsExpanded: (viewsExpanded) => set({ viewsExpanded }),
  searchQuery: '',
  setSearchQuery: (searchQuery) => set({ searchQuery }),

  // Insights view
  insightsData: null,
  setInsightsData: (insightsData) => set({ insightsData }),
  insightsLoading: false,
  setInsightsLoading: (insightsLoading) => set({ insightsLoading }),
  insightsError: null,
  setInsightsError: (insightsError) => set({ insightsError }),

  // Pipeline metadata
  metadata: null,
  setMetadata: (metadata) => set({ metadata }),

  // Embedding status
  embeddingStatus: { status: 'idle', updated_at: null, error: null },
  setEmbeddingStatus: (embeddingStatus) => set({ embeddingStatus }),

  // Reset
  reset: () =>
    set({
      metadata: null,
      embeddingStatus: { status: 'idle', updated_at: null, error: null },
      selectedTable: null,
      selectedView: null,
      isModalOpen: false,
      isViewModalOpen: false,
      searchQuery: '',
      insightsData: null,
      insightsError: null,
      insightsLoading: false,
      connectionError: null,
      successMessage: null,
      loading: false,
      validationErrors: {},
      sqlFile: null,
      connectionName: '',
      connectionDescription: '',
    }),
}));
