import { create } from 'zustand';
import type { Message } from '@/types/api';

interface SessionState {
  // Session data
  sessionId: string | null;
  messages: Message[];

  // UI state
  isLoading: boolean;
  isStreaming: boolean;
  error: string | null;

  // Streaming state
  streamingContent: string;

  // Actions
  setSessionId: (sessionId: string | null) => void;
  addMessage: (message: Message) => void;
  setMessages: (messages: Message[]) => void;
  clearMessages: () => void;
  setLoading: (isLoading: boolean) => void;
  setStreaming: (isStreaming: boolean) => void;
  setError: (error: string | null) => void;
  appendStreamingContent: (content: string) => void;
  clearStreamingContent: () => void;
  finalizeStreamingMessage: () => void;
  reset: () => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  // Initial state
  sessionId: null,
  messages: [],
  isLoading: false,
  isStreaming: false,
  error: null,
  streamingContent: '',

  // Actions
  setSessionId: (sessionId) => set({ sessionId }),

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  setMessages: (messages) => set({ messages }),

  clearMessages: () => set({ messages: [], streamingContent: '' }),

  setLoading: (isLoading) => set({ isLoading }),

  setStreaming: (isStreaming) => set({ isStreaming }),

  setError: (error) => set({ error }),

  appendStreamingContent: (content) =>
    set((state) => ({
      streamingContent: state.streamingContent + content,
    })),

  clearStreamingContent: () => set({ streamingContent: '' }),

  finalizeStreamingMessage: () => {
    const { streamingContent, messages } = get();
    if (streamingContent) {
      set({
        messages: [
          ...messages,
          {
            role: 'assistant',
            content: streamingContent,
            timestamp: new Date().toISOString(),
          },
        ],
        streamingContent: '',
        isStreaming: false,
      });
    }
  },

  reset: () =>
    set({
      sessionId: null,
      messages: [],
      isLoading: false,
      isStreaming: false,
      error: null,
      streamingContent: '',
    }),
}));
