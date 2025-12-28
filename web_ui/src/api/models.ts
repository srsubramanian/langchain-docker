import { apiClient } from './client';
import type { ProviderInfo, ProviderDetails, HealthResponse, StatusResponse } from '@/types/api';

export const modelsApi = {
  async listProviders(): Promise<ProviderInfo[]> {
    const { data } = await apiClient.get<ProviderInfo[]>('/api/v1/models/providers');
    return data;
  },

  async getProviderDetails(provider: string): Promise<ProviderDetails> {
    const { data } = await apiClient.get<ProviderDetails>(`/api/v1/models/providers/${provider}`);
    return data;
  },

  async validate(provider: string, model: string, temperature: number): Promise<{
    valid: boolean;
    provider: string;
    model: string;
    message: string;
    error?: string;
    setup_url?: string;
  }> {
    const { data } = await apiClient.post('/api/v1/models/validate', {
      provider,
      model,
      temperature,
    });
    return data;
  },

  async healthCheck(): Promise<HealthResponse> {
    const { data } = await apiClient.get<HealthResponse>('/health');
    return data;
  },

  async getStatus(): Promise<StatusResponse> {
    const { data } = await apiClient.get<StatusResponse>('/api/v1/status');
    return data;
  },
};
