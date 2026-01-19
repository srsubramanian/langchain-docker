import { create } from 'zustand';
import { knowledgeBaseApi } from '@/api/knowledgeBase';
import type {
  KBStats,
  KBDocument,
  KBCollection,
  KBSearchResult,
} from '@/types/api';

interface KnowledgeBaseState {
  // Data
  stats: KBStats | null;
  documents: KBDocument[];
  recentDocuments: KBDocument[];
  collections: KBCollection[];
  searchResults: KBSearchResult[];
  searchQuery: string;

  // UI State
  isLoading: boolean;
  isSearching: boolean;
  isUploading: boolean;
  error: string | null;

  // Actions
  fetchStats: () => Promise<void>;
  fetchDocuments: (collection?: string | null) => Promise<void>;
  fetchRecentDocuments: (limit?: number) => Promise<void>;
  fetchCollections: () => Promise<void>;
  uploadDocument: (content: string, filename: string, collection?: string | null) => Promise<KBDocument>;
  uploadFile: (file: File, collection?: string | null) => Promise<KBDocument>;
  deleteDocument: (id: string) => Promise<void>;
  search: (query: string, topK?: number, collection?: string | null) => Promise<void>;
  clearSearch: () => void;
  clearError: () => void;
  refresh: () => Promise<void>;
}

export const useKnowledgeBaseStore = create<KnowledgeBaseState>()((set, get) => ({
  // Initial state
  stats: null,
  documents: [],
  recentDocuments: [],
  collections: [],
  searchResults: [],
  searchQuery: '',
  isLoading: false,
  isSearching: false,
  isUploading: false,
  error: null,

  fetchStats: async () => {
    try {
      set({ isLoading: true, error: null });
      const stats = await knowledgeBaseApi.getStats();
      set({ stats, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch stats',
        isLoading: false,
      });
    }
  },

  fetchDocuments: async (collection?: string | null) => {
    try {
      set({ isLoading: true, error: null });
      const response = await knowledgeBaseApi.listDocuments(collection);
      set({ documents: response.documents, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch documents',
        isLoading: false,
      });
    }
  },

  fetchRecentDocuments: async (limit: number = 10) => {
    try {
      set({ isLoading: true, error: null });
      const response = await knowledgeBaseApi.listDocuments(null, limit);
      // Sort by created_at descending to get most recent
      const sorted = [...response.documents].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      set({ recentDocuments: sorted.slice(0, limit), isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch recent documents',
        isLoading: false,
      });
    }
  },

  fetchCollections: async () => {
    try {
      set({ isLoading: true, error: null });
      const response = await knowledgeBaseApi.listCollections();
      set({ collections: response.collections, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch collections',
        isLoading: false,
      });
    }
  },

  uploadDocument: async (content: string, filename: string, collection?: string | null) => {
    try {
      set({ isUploading: true, error: null });
      const response = await knowledgeBaseApi.uploadDocument({
        content,
        filename,
        collection,
      });
      // Refresh data
      await get().refresh();
      set({ isUploading: false });
      return response.document;
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to upload document',
        isUploading: false,
      });
      throw error;
    }
  },

  uploadFile: async (file: File, collection?: string | null) => {
    try {
      set({ isUploading: true, error: null });
      const response = await knowledgeBaseApi.uploadFile(file, collection);
      // Refresh data
      await get().refresh();
      set({ isUploading: false });
      return response.document;
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to upload file',
        isUploading: false,
      });
      throw error;
    }
  },

  deleteDocument: async (id: string) => {
    try {
      set({ isLoading: true, error: null });
      await knowledgeBaseApi.deleteDocument(id);
      // Refresh data
      await get().refresh();
      set({ isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to delete document',
        isLoading: false,
      });
      throw error;
    }
  },

  search: async (query: string, topK: number = 5, collection?: string | null) => {
    if (!query.trim()) {
      set({ searchResults: [], searchQuery: '' });
      return;
    }

    try {
      set({ isSearching: true, error: null, searchQuery: query });
      const response = await knowledgeBaseApi.search({
        query,
        top_k: topK,
        collection,
      });
      set({ searchResults: response.results, isSearching: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to search',
        isSearching: false,
      });
    }
  },

  clearSearch: () => {
    set({ searchResults: [], searchQuery: '' });
  },

  clearError: () => {
    set({ error: null });
  },

  refresh: async () => {
    const { fetchStats, fetchRecentDocuments, fetchCollections } = get();
    await Promise.all([
      fetchStats(),
      fetchRecentDocuments(),
      fetchCollections(),
    ]);
  },
}));
