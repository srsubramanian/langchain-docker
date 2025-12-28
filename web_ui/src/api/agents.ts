import { apiClient } from './client';
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
