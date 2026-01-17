import { apiClient } from './client';
import type { Capability, CapabilityListResponse } from '@/types/api';

export const capabilitiesApi = {
  /**
   * List all available capabilities (unified tools and skills).
   */
  list: async (): Promise<CapabilityListResponse> => {
    const response = await apiClient.get<CapabilityListResponse>('/api/v1/capabilities');
    return response.data;
  },

  /**
   * List capability categories.
   */
  listCategories: async (): Promise<string[]> => {
    const response = await apiClient.get<{ categories: string[] }>('/api/v1/capabilities/categories');
    return response.data.categories;
  },

  /**
   * Get capabilities by category.
   */
  listByCategory: async (category: string): Promise<CapabilityListResponse> => {
    const response = await apiClient.get<CapabilityListResponse>(`/api/v1/capabilities/category/${category}`);
    return response.data;
  },

  /**
   * Get a specific capability.
   */
  get: async (id: string): Promise<Capability> => {
    const response = await apiClient.get<Capability>(`/api/v1/capabilities/${id}`);
    return response.data;
  },

  /**
   * Load capability content (for skill bundles).
   */
  load: async (id: string): Promise<{ capability_id: string; name: string; content: string }> => {
    const response = await apiClient.get<{ capability_id: string; name: string; content: string }>(
      `/api/v1/capabilities/${id}/load`
    );
    return response.data;
  },
};
