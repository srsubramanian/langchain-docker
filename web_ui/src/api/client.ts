import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000,
});

// Request interceptor for logging
apiClient.interceptors.request.use((config) => {
  if (import.meta.env.DEV) {
    console.debug('[API]', config.method?.toUpperCase(), config.url);
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
