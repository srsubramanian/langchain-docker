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
  createServer: (url: string, name?: string) => Promise<void>;
  deleteServer: (serverId: string) => Promise<void>;
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
          // Update server status in state with tool count
          const { servers } = get();
          set({
            servers: servers.map((s) =>
              s.id === serverId
                ? {
                    ...s,
                    status: result.status,
                    tools: result.tools,
                    tool_count: result.tools?.length ?? null,
                  }
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
          // Update server status in state - clear tool cache but keep status available
          const { servers } = get();
          set({
            servers: servers.map((s) =>
              s.id === serverId
                ? { ...s, status: 'available', tools: null, tool_count: null }
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

      createServer: async (url, name) => {
        set({ loading: true, error: null });
        try {
          await mcpApi.createServer({ url, name });
          // Refresh server list
          await get().fetchServers();
        } catch (err) {
          set({
            error: err instanceof Error ? err.message : 'Failed to add MCP server',
            loading: false,
          });
          throw err;
        }
      },

      deleteServer: async (serverId) => {
        set({ loading: true, error: null });
        try {
          await mcpApi.deleteServer(serverId);
          // Remove from local state
          const { servers, enabledServerIds } = get();
          set({
            servers: servers.filter((s) => s.id !== serverId),
            enabledServerIds: enabledServerIds.filter((id) => id !== serverId),
            loading: false,
          });
        } catch (err) {
          set({
            error: err instanceof Error ? err.message : 'Failed to delete MCP server',
            loading: false,
          });
          throw err;
        }
      },

      setError: (error) => set({ error }),

      getEnabledServers: () => {
        const { enabledServerIds, servers } = get();
        // If servers haven't been fetched yet, return all enabled IDs
        // (user explicitly selected these, so trust their selection)
        if (servers.length === 0) {
          return enabledServerIds;
        }
        // Only return IDs of servers that exist and are enabled in config
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
