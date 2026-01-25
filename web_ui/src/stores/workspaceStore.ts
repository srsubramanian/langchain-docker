import { create } from 'zustand';
import type { WorkspaceFileInfo, WorkspaceInfo } from '@/types/api';
import { workspaceApi } from '@/api/workspace';

interface WorkspaceState {
  // Data
  info: WorkspaceInfo | null;
  files: WorkspaceFileInfo[];

  // UI state
  isLoading: boolean;
  isUploading: boolean;
  error: string | null;
  isOpen: boolean;

  // Actions
  setOpen: (isOpen: boolean) => void;
  toggleOpen: () => void;
  fetchInfo: (sessionId: string) => Promise<void>;
  fetchFiles: (sessionId: string) => Promise<void>;
  uploadFile: (sessionId: string, file: File) => Promise<void>;
  deleteFile: (sessionId: string, filename: string) => Promise<void>;
  downloadFile: (sessionId: string, filename: string) => Promise<void>;
  clearWorkspace: (sessionId: string) => Promise<void>;
  reset: () => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  // Initial state
  info: null,
  files: [],
  isLoading: false,
  isUploading: false,
  error: null,
  isOpen: false,

  // Actions
  setOpen: (isOpen) => set({ isOpen }),

  toggleOpen: () => set((state) => ({ isOpen: !state.isOpen })),

  fetchInfo: async (sessionId) => {
    if (!sessionId) return;
    set({ isLoading: true, error: null });
    try {
      const info = await workspaceApi.getInfo(sessionId);
      set({ info, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch workspace info',
        isLoading: false,
      });
    }
  },

  fetchFiles: async (sessionId) => {
    if (!sessionId) return;
    set({ isLoading: true, error: null });
    try {
      const response = await workspaceApi.listFiles(sessionId);
      set({ files: response.files, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch files',
        isLoading: false,
      });
    }
  },

  uploadFile: async (sessionId, file) => {
    if (!sessionId) return;
    set({ isUploading: true, error: null });
    try {
      await workspaceApi.uploadFile(sessionId, file);
      // Refresh file list after upload
      const response = await workspaceApi.listFiles(sessionId);
      set({ files: response.files, isUploading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to upload file',
        isUploading: false,
      });
    }
  },

  deleteFile: async (sessionId, filename) => {
    if (!sessionId) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.deleteFile(sessionId, filename);
      // Update local state
      set((state) => ({
        files: state.files.filter((f) => f.filename !== filename),
        isLoading: false,
      }));
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to delete file',
        isLoading: false,
      });
    }
  },

  downloadFile: async (sessionId, filename) => {
    if (!sessionId) return;
    try {
      const blob = await workspaceApi.downloadFile(sessionId, filename);
      // Create download link
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to download file',
      });
    }
  },

  clearWorkspace: async (sessionId) => {
    if (!sessionId) return;
    set({ isLoading: true, error: null });
    try {
      await workspaceApi.deleteWorkspace(sessionId);
      set({ files: [], info: null, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to clear workspace',
        isLoading: false,
      });
    }
  },

  reset: () =>
    set({
      info: null,
      files: [],
      isLoading: false,
      isUploading: false,
      error: null,
      isOpen: false,
    }),
}));
