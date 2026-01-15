import { apiClient } from './client';
import type {
  MCPServersResponse,
  MCPServerInfo,
  MCPServerStartResponse,
  MCPServerStopResponse,
  MCPToolsResponse,
  MCPToolCallRequest,
  MCPToolCallResponse,
} from '@/types/api';

export const mcpApi = {
  /**
   * List all configured MCP servers with their status.
   */
  async listServers(): Promise<MCPServerInfo[]> {
    const { data } = await apiClient.get<MCPServersResponse>('/api/v1/mcp/servers');
    return data.servers;
  },

  /**
   * Start an MCP server and discover its tools.
   */
  async startServer(serverId: string): Promise<MCPServerStartResponse> {
    const { data } = await apiClient.post<MCPServerStartResponse>(
      `/api/v1/mcp/servers/${serverId}/start`
    );
    return data;
  },

  /**
   * Stop a running MCP server.
   */
  async stopServer(serverId: string): Promise<MCPServerStopResponse> {
    const { data } = await apiClient.post<MCPServerStopResponse>(
      `/api/v1/mcp/servers/${serverId}/stop`
    );
    return data;
  },

  /**
   * Get tools available from an MCP server.
   * Starts the server if not already running.
   */
  async getServerTools(serverId: string): Promise<MCPToolsResponse> {
    const { data } = await apiClient.get<MCPToolsResponse>(
      `/api/v1/mcp/servers/${serverId}/tools`
    );
    return data;
  },

  /**
   * Call a tool on an MCP server.
   */
  async callTool(
    serverId: string,
    request: MCPToolCallRequest
  ): Promise<MCPToolCallResponse> {
    const { data } = await apiClient.post<MCPToolCallResponse>(
      `/api/v1/mcp/servers/${serverId}/tools/call`,
      request
    );
    return data;
  },
};
