import { apiClient } from './client';
import type {
  WorkspaceInfo,
  WorkspaceFileListResponse,
  WorkspaceFileUploadResponse,
  WorkspaceFileContentResponse,
  WorkspaceFileDeleteResponse,
  WorkspaceDeleteResponse,
  WorkspaceWriteFileRequest,
} from '@/types/api';

export const workspaceApi = {
  /**
   * Get workspace info for a session
   */
  async getInfo(sessionId: string): Promise<WorkspaceInfo> {
    const { data } = await apiClient.get<WorkspaceInfo>(
      `/api/v1/sessions/${sessionId}/workspace`
    );
    return data;
  },

  /**
   * List all files in a session's workspace
   */
  async listFiles(sessionId: string): Promise<WorkspaceFileListResponse> {
    const { data } = await apiClient.get<WorkspaceFileListResponse>(
      `/api/v1/sessions/${sessionId}/workspace/files`
    );
    return data;
  },

  /**
   * Upload a file to the workspace
   */
  async uploadFile(sessionId: string, file: File): Promise<WorkspaceFileUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const { data } = await apiClient.post<WorkspaceFileUploadResponse>(
      `/api/v1/sessions/${sessionId}/workspace/files`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return data;
  },

  /**
   * Write text content to a file in the workspace
   */
  async writeFile(
    sessionId: string,
    request: WorkspaceWriteFileRequest
  ): Promise<WorkspaceFileUploadResponse> {
    const { data } = await apiClient.post<WorkspaceFileUploadResponse>(
      `/api/v1/sessions/${sessionId}/workspace/files/write`,
      request
    );
    return data;
  },

  /**
   * Read file content from the workspace
   */
  async readFile(
    sessionId: string,
    filename: string,
    maxBytes?: number
  ): Promise<WorkspaceFileContentResponse> {
    const params = maxBytes ? { max_bytes: maxBytes } : undefined;
    const { data } = await apiClient.get<WorkspaceFileContentResponse>(
      `/api/v1/sessions/${sessionId}/workspace/files/${encodeURIComponent(filename)}/content`,
      { params }
    );
    return data;
  },

  /**
   * Download a file from the workspace
   */
  async downloadFile(sessionId: string, filename: string): Promise<Blob> {
    const { data } = await apiClient.get<Blob>(
      `/api/v1/sessions/${sessionId}/workspace/files/${encodeURIComponent(filename)}`,
      { responseType: 'blob' }
    );
    return data;
  },

  /**
   * Delete a file from the workspace
   */
  async deleteFile(sessionId: string, filename: string): Promise<WorkspaceFileDeleteResponse> {
    const { data } = await apiClient.delete<WorkspaceFileDeleteResponse>(
      `/api/v1/sessions/${sessionId}/workspace/files/${encodeURIComponent(filename)}`
    );
    return data;
  },

  /**
   * Delete the entire workspace for a session
   */
  async deleteWorkspace(sessionId: string): Promise<WorkspaceDeleteResponse> {
    const { data } = await apiClient.delete<WorkspaceDeleteResponse>(
      `/api/v1/sessions/${sessionId}/workspace`
    );
    return data;
  },
};
