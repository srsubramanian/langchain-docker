import { apiClient } from './client';
import type { SessionCreate, SessionResponse, SessionList } from '@/types/api';

export const sessionsApi = {
  async create(request: SessionCreate = {}): Promise<SessionResponse> {
    const { data } = await apiClient.post<SessionResponse>('/api/v1/sessions', request);
    return data;
  },

  async get(sessionId: string): Promise<SessionResponse> {
    const { data } = await apiClient.get<SessionResponse>(`/api/v1/sessions/${sessionId}`);
    return data;
  },

  async list(limit = 10, offset = 0): Promise<SessionList> {
    const { data } = await apiClient.get<SessionList>('/api/v1/sessions', {
      params: { limit, offset },
    });
    return data;
  },

  async delete(sessionId: string): Promise<void> {
    await apiClient.delete(`/api/v1/sessions/${sessionId}`);
  },

  async clearAll(): Promise<{ deleted_count: number }> {
    const { data } = await apiClient.delete<{ deleted_count: number }>('/api/v1/sessions');
    return data;
  },
};
