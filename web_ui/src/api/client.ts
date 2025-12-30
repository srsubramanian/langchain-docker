import axios from 'axios';
import { useUserStore } from '@/stores/userStore';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000,
});

// Request interceptor for adding user ID header and logging
apiClient.interceptors.request.use((config) => {
  // Add X-User-ID header from user store
  const userId = useUserStore.getState().currentUserId;
  if (userId) {
    config.headers['X-User-ID'] = userId;
  }

  if (import.meta.env.DEV) {
    console.debug('[API]', config.method?.toUpperCase(), config.url, userId ? `(User: ${userId})` : '');
  }
  return config;
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('[API Error]', error.response?.data || error.message);
    throw error;
  }
);

export { API_BASE_URL };
