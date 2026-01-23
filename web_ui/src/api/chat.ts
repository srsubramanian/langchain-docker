import { apiClient, API_BASE_URL } from './client';
import { useUserStore } from '@/stores/userStore';
import type { ChatRequest, ChatResponse, StreamEvent } from '@/types/api';

export const chatApi = {
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const { data } = await apiClient.post<ChatResponse>('/api/v1/chat', request);
    return data;
  },

  async *streamMessage(request: ChatRequest, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
    const userId = useUserStore.getState().currentUserId;
    const response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(userId && { 'X-User-ID': userId }),
      },
      body: JSON.stringify({ ...request, stream: true }),
      signal, // Pass abort signal to fetch
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
};
