import { apiClient, API_BASE_URL } from './client';
import { useUserStore } from '@/stores/userStore';
import type {
  AgentInfo,
  ToolTemplate,
  CustomAgentInfo,
  CustomAgentCreateRequest,
  CustomAgentCreateResponse,
  WorkflowInfo,
  WorkflowCreateRequest,
  WorkflowCreateResponse,
  WorkflowInvokeRequest,
  WorkflowInvokeResponse,
  DirectInvokeRequest,
  DirectInvokeResponse,
  StreamEvent,
} from '@/types/api';

// Unified agent info type
export interface UnifiedAgentInfo {
  id: string;
  name: string;
  type: 'builtin' | 'custom';
  tools: string[];
  skills?: string[];
  description: string;
  system_prompt?: string;
  provider?: string;
  model?: string;
  temperature?: number;
  schedule?: {
    enabled: boolean;
    cron_expression: string;
    trigger_prompt: string;
    timezone: string;
    next_run?: string;
  };
  created_at?: string;
}

export const agentsApi = {
  // =============================================================================
  // UNIFIED AGENT ENDPOINTS (NEW)
  // =============================================================================

  /**
   * List all agents (both custom and built-in)
   */
  async listAllAgents(agentType?: 'builtin' | 'custom'): Promise<UnifiedAgentInfo[]> {
    const params = agentType ? { agent_type: agentType } : undefined;
    const { data } = await apiClient.get<UnifiedAgentInfo[]>('/api/v1/agents', { params });
    return data;
  },

  /**
   * Get details of any agent (custom or built-in)
   */
  async getAgent(agentId: string): Promise<UnifiedAgentInfo> {
    const { data } = await apiClient.get<UnifiedAgentInfo>(`/api/v1/agents/${agentId}`);
    return data;
  },

  /**
   * Create a custom agent
   */
  async createAgent(request: CustomAgentCreateRequest): Promise<CustomAgentCreateResponse> {
    const { data } = await apiClient.post<CustomAgentCreateResponse>('/api/v1/agents', request);
    return data;
  },

  /**
   * Delete a custom agent (built-in agents cannot be deleted)
   */
  async deleteAgent(agentId: string): Promise<{ agent_id: string; deleted: boolean }> {
    const { data } = await apiClient.delete<{ agent_id: string; deleted: boolean }>(`/api/v1/agents/${agentId}`);
    return data;
  },

  /**
   * Invoke any agent (custom or built-in) - non-streaming
   */
  async invokeAgent(agentId: string, request: DirectInvokeRequest): Promise<DirectInvokeResponse> {
    const { data } = await apiClient.post<DirectInvokeResponse>(
      `/api/v1/agents/${agentId}/invoke`,
      request,
      { timeout: 120000 } // 2 minute timeout for agent execution
    );
    return data;
  },

  /**
   * Invoke any agent (custom or built-in) - streaming with SSE
   */
  async *invokeAgentStream(agentId: string, request: DirectInvokeRequest): AsyncGenerator<StreamEvent> {
    const userId = useUserStore.getState().currentUserId;
    const response = await fetch(`${API_BASE_URL}/api/v1/agents/${agentId}/invoke/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(userId && { 'X-User-ID': userId }),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Request failed' }));
      yield { event: 'error', error: error.message || error.error || 'Request failed' };
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      yield { event: 'error', error: 'No response body' };
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let currentEvent = 'message';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        if (trimmed.startsWith('event: ')) {
          currentEvent = trimmed.slice(7);
        } else if (trimmed.startsWith('data: ')) {
          try {
            const data = JSON.parse(trimmed.slice(6));
            yield { event: currentEvent as StreamEvent['event'], ...data };
          } catch {
            // Skip malformed JSON
          }
        }
      }
    }
  },

  /**
   * Clear an agent's session history
   */
  async clearAgentSession(agentId: string, sessionId?: string): Promise<void> {
    await apiClient.delete(`/api/v1/agents/${agentId}/session`, {
      params: sessionId ? { session_id: sessionId } : undefined,
    });
  },

  // =============================================================================
  // TOOL REGISTRY ENDPOINTS
  // =============================================================================

  async listTools(): Promise<ToolTemplate[]> {
    const { data } = await apiClient.get<ToolTemplate[]>('/api/v1/agents/tools');
    return data;
  },

  async listToolCategories(): Promise<string[]> {
    const { data } = await apiClient.get<string[]>('/api/v1/agents/tools/categories');
    return data;
  },

  // =============================================================================
  // LEGACY ENDPOINTS (kept for backward compatibility)
  // Use unified endpoints above instead
  // =============================================================================

  /**
   * @deprecated Use listAllAgents('builtin') instead
   */
  async listBuiltin(): Promise<AgentInfo[]> {
    const { data } = await apiClient.get<AgentInfo[]>('/api/v1/agents/builtin');
    return data;
  },

  /**
   * @deprecated Use listAllAgents('custom') instead
   */
  async listCustomAgents(): Promise<CustomAgentInfo[]> {
    const { data } = await apiClient.get<CustomAgentInfo[]>('/api/v1/agents/custom');
    return data;
  },

  /**
   * @deprecated Use createAgent() instead
   */
  async createCustomAgent(request: CustomAgentCreateRequest): Promise<CustomAgentCreateResponse> {
    return this.createAgent(request);
  },

  /**
   * @deprecated Use getAgent() instead
   */
  async getCustomAgent(agentId: string): Promise<CustomAgentInfo> {
    const { data } = await apiClient.get<CustomAgentInfo>(`/api/v1/agents/custom/${agentId}`);
    return data;
  },

  /**
   * @deprecated Use deleteAgent() instead
   */
  async deleteCustomAgent(agentId: string): Promise<{ agent_id: string; message: string }> {
    const { data } = await apiClient.delete<{ agent_id: string; message: string }>(`/api/v1/agents/custom/${agentId}`);
    return data;
  },

  /**
   * @deprecated Use invokeAgent() instead
   */
  async invokeAgentDirect(agentId: string, request: DirectInvokeRequest): Promise<DirectInvokeResponse> {
    return this.invokeAgent(agentId, request);
  },

  /**
   * @deprecated Use invokeAgentStream() instead
   */
  async *invokeAgentDirectStream(agentId: string, request: DirectInvokeRequest): AsyncGenerator<StreamEvent> {
    yield* this.invokeAgentStream(agentId, request);
  },

  // =============================================================================
  // WORKFLOW ENDPOINTS
  // =============================================================================

  async listWorkflows(): Promise<WorkflowInfo[]> {
    const { data } = await apiClient.get<WorkflowInfo[]>('/api/v1/workflows');
    return data;
  },

  async createWorkflow(request: WorkflowCreateRequest): Promise<WorkflowCreateResponse> {
    const { data } = await apiClient.post<WorkflowCreateResponse>('/api/v1/workflows', request);
    return data;
  },

  async invokeWorkflow(workflowId: string, request: WorkflowInvokeRequest): Promise<WorkflowInvokeResponse> {
    const { data } = await apiClient.post<WorkflowInvokeResponse>(
      `/api/v1/workflows/${workflowId}/invoke`,
      request,
      { timeout: 120000 } // 2 minute timeout for workflow execution
    );
    return data;
  },

  /**
   * Invoke a workflow with streaming - returns SSE events
   */
  async *invokeWorkflowStream(workflowId: string, request: WorkflowInvokeRequest): AsyncGenerator<StreamEvent> {
    const userId = useUserStore.getState().currentUserId;
    const response = await fetch(`${API_BASE_URL}/api/v1/workflows/${workflowId}/invoke/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(userId && { 'X-User-ID': userId }),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Request failed' }));
      yield { event: 'error', error: error.message || error.error || 'Request failed' };
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      yield { event: 'error', error: 'No response body' };
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let currentEvent = 'message';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        if (trimmed.startsWith('event: ')) {
          currentEvent = trimmed.slice(7);
        } else if (trimmed.startsWith('data: ')) {
          try {
            const data = JSON.parse(trimmed.slice(6));
            yield { event: currentEvent as StreamEvent['event'], ...data };
          } catch {
            // Skip malformed JSON
          }
        }
      }
    }
  },

  async deleteWorkflow(workflowId: string): Promise<{ workflow_id: string; message: string }> {
    const { data } = await apiClient.delete<{ workflow_id: string; message: string }>(`/api/v1/workflows/${workflowId}`);
    return data;
  },
};
