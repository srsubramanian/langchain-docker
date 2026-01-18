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

export const agentsApi = {
  // Built-in agents
  async listBuiltin(): Promise<AgentInfo[]> {
    const { data } = await apiClient.get<AgentInfo[]>('/api/v1/agents/builtin');
    return data;
  },

  // Tool registry
  async listTools(): Promise<ToolTemplate[]> {
    const { data } = await apiClient.get<ToolTemplate[]>('/api/v1/agents/tools');
    return data;
  },

  async listToolCategories(): Promise<string[]> {
    const { data } = await apiClient.get<string[]>('/api/v1/agents/tools/categories');
    return data;
  },

  // Custom agents
  async listCustomAgents(): Promise<CustomAgentInfo[]> {
    const { data } = await apiClient.get<CustomAgentInfo[]>('/api/v1/agents/custom');
    return data;
  },

  async createCustomAgent(request: CustomAgentCreateRequest): Promise<CustomAgentCreateResponse> {
    const { data } = await apiClient.post<CustomAgentCreateResponse>('/api/v1/agents/custom', request);
    return data;
  },

  async getCustomAgent(agentId: string): Promise<CustomAgentInfo> {
    const { data } = await apiClient.get<CustomAgentInfo>(`/api/v1/agents/custom/${agentId}`);
    return data;
  },

  async deleteCustomAgent(agentId: string): Promise<{ agent_id: string; message: string }> {
    const { data } = await apiClient.delete<{ agent_id: string; message: string }>(`/api/v1/agents/custom/${agentId}`);
    return data;
  },

  // Direct agent invocation (no supervisor) for human-in-the-loop
  async invokeAgentDirect(agentId: string, request: DirectInvokeRequest): Promise<DirectInvokeResponse> {
    const { data } = await apiClient.post<DirectInvokeResponse>(
      `/api/v1/agents/custom/${agentId}/invoke`,
      request,
      { timeout: 120000 } // 2 minute timeout for agent execution
    );
    return data;
  },

  // Streaming direct agent invocation with SSE
  async *invokeAgentDirectStream(agentId: string, request: DirectInvokeRequest): AsyncGenerator<StreamEvent> {
    const userId = useUserStore.getState().currentUserId;
    const response = await fetch(`${API_BASE_URL}/api/v1/agents/custom/${agentId}/invoke/stream`, {
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

  async clearAgentSession(agentId: string, sessionId?: string): Promise<void> {
    await apiClient.delete(`/api/v1/agents/custom/${agentId}/session`, {
      params: sessionId ? { session_id: sessionId } : undefined,
    });
  },

  // Workflows
  async listWorkflows(): Promise<WorkflowInfo[]> {
    const { data } = await apiClient.get<WorkflowInfo[]>('/api/v1/agents/workflows');
    return data;
  },

  async createWorkflow(request: WorkflowCreateRequest): Promise<WorkflowCreateResponse> {
    const { data } = await apiClient.post<WorkflowCreateResponse>('/api/v1/agents/workflows', request);
    return data;
  },

  async invokeWorkflow(workflowId: string, request: WorkflowInvokeRequest): Promise<WorkflowInvokeResponse> {
    const { data } = await apiClient.post<WorkflowInvokeResponse>(
      `/api/v1/agents/workflows/${workflowId}/invoke`,
      request,
      { timeout: 120000 } // 2 minute timeout for workflow execution
    );
    return data;
  },

  async deleteWorkflow(workflowId: string): Promise<{ workflow_id: string; message: string }> {
    const { data } = await apiClient.delete<{ workflow_id: string; message: string }>(`/api/v1/agents/workflows/${workflowId}`);
    return data;
  },
};
