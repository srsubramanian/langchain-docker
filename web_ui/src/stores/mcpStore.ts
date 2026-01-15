import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { MCPServerInfo } from '@/types/api';
import { mcpApi } from '@/api';

interface MCPState {
  // Server state
  servers: MCPServerInfo[];
  enabledServerIds: string[];
  loading: boolean;
  error: string | null;

  // Actions
  fetchServers: () => Promise<void>;
  toggleServer: (serverId: string) => void;
  enableServer: (serverId: string) => void;
  disableServer: (serverId: string) => void;
  startServer: (serverId: string) => Promise<void>;
  stopServer: (serverId: string) => Promise<void>;
  setError: (error: string | null) => void;
  getEnabledServers: () => string[];
}

export const useMCPStore = create<MCPState>()(
  persist(
    (set, get) => ({
      servers: [],
      enabledServerIds: [],
      loading: false,
      error: null,

      fetchServers: async () => {
        set({ loading: true, error: null });
        try {
          const servers = await mcpApi.listServers();
          set({ servers, loading: false });
        } catch (err) {
          set({
            error: err instanceof Error ? err.message : 'Failed to fetch MCP servers',
            loading: false,
          });
        }
      },

      toggleServer: (serverId) => {
        const { enabledServerIds } = get();
        if (enabledServerIds.includes(serverId)) {
          set({ enabledServerIds: enabledServerIds.filter((id) => id !== serverId) });
        } else {
          set({ enabledServerIds: [...enabledServerIds, serverId] });
        }
      },

      enableServer: (serverId) => {
        const { enabledServerIds } = get();
        if (!enabledServerIds.includes(serverId)) {
          set({ enabledServerIds: [...enabledServerIds, serverId] });
        }
      },

      disableServer: (serverId) => {
        const { enabledServerIds } = get();
        set({ enabledServerIds: enabledServerIds.filter((id) => id !== serverId) });
      },

      startServer: async (serverId) => {
        set({ loading: true, error: null });
        try {
          const result = await mcpApi.startServer(serverId);
          // Update server status in state
          const { servers } = get();
          set({
            servers: servers.map((s) =>
              s.id === serverId
                ? { ...s, status: result.status, tools: result.tools }
                : s
            ),
            loading: false,
          });
        } catch (err) {
          set({
            error: err instanceof Error ? err.message : 'Failed to start MCP server',
            loading: false,
          });
        }
      },

      stopServer: async (serverId) => {
        set({ loading: true, error: null });
        try {
          await mcpApi.stopServer(serverId);
          // Update server status in state
          const { servers } = get();
          set({
            servers: servers.map((s) =>
              s.id === serverId
                ? { ...s, status: 'stopped', tools: null }
                : s
            ),
            loading: false,
          });
        } catch (err) {
          set({
            error: err instanceof Error ? err.message : 'Failed to stop MCP server',
            loading: false,
          });
        }
      },

      setError: (error) => set({ error }),

      getEnabledServers: () => {
        const { enabledServerIds, servers } = get();
        // Only return IDs of servers that exist and are enabled
        return enabledServerIds.filter((id) =>
          servers.some((s) => s.id === id && s.enabled)
        );
      },
    }),
    {
      name: 'langchain-mcp',
      partialize: (state) => ({
        // Only persist enabledServerIds, not server data
        enabledServerIds: state.enabledServerIds,
      }),
    }
  )
);
