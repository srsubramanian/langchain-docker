/**
 * Knowledge Base API client for RAG functionality.
 */

import type {
  KBStats,
  KBDocument,
  KBDocumentListResponse,
  KBCollectionListResponse,
  KBSearchRequest,
  KBSearchResponse,
  KBDocumentUploadRequest,
  KBFileUploadResponse,
  KBDeleteResponse,
  KBContextResponse,
} from '@/types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

class KnowledgeBaseApi {
  /**
   * Get knowledge base statistics.
   */
  async getStats(): Promise<KBStats> {
    const response = await fetch(`${API_BASE_URL}/api/v1/kb/stats`);
    if (!response.ok) {
      throw new Error(`Failed to get KB stats: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * List all documents in the knowledge base.
   */
  async listDocuments(
    collection?: string | null,
    limit: number = 100,
    offset: number = 0
  ): Promise<KBDocumentListResponse> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    if (collection) {
      params.append('collection', collection);
    }
    const response = await fetch(`${API_BASE_URL}/api/v1/kb/documents?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to list documents: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Get a document by ID.
   */
  async getDocument(documentId: string): Promise<KBDocument> {
    const response = await fetch(`${API_BASE_URL}/api/v1/kb/documents/${documentId}`);
    if (!response.ok) {
      throw new Error(`Failed to get document: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Upload text content as a document.
   */
  async uploadDocument(request: KBDocumentUploadRequest): Promise<KBFileUploadResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/kb/documents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'Failed to upload document');
    }
    return response.json();
  }

  /**
   * Upload a file to the knowledge base.
   */
  async uploadFile(
    file: File,
    collection?: string | null
  ): Promise<KBFileUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (collection) {
      formData.append('collection', collection);
    }

    const response = await fetch(`${API_BASE_URL}/api/v1/kb/documents/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'Failed to upload file');
    }
    return response.json();
  }

  /**
   * Delete a document from the knowledge base.
   */
  async deleteDocument(documentId: string): Promise<KBDeleteResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/kb/documents/${documentId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`Failed to delete document: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Search the knowledge base.
   */
  async search(request: KBSearchRequest): Promise<KBSearchResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/kb/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      throw new Error(`Failed to search: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * List all collections.
   */
  async listCollections(): Promise<KBCollectionListResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/kb/collections`);
    if (!response.ok) {
      throw new Error(`Failed to list collections: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Get formatted context for RAG.
   */
  async getContext(
    query: string,
    topK: number = 5,
    minScore: number = 0,
    collection?: string | null
  ): Promise<KBContextResponse> {
    const params = new URLSearchParams({
      query,
      top_k: topK.toString(),
      min_score: minScore.toString(),
    });
    if (collection) {
      params.append('collection', collection);
    }
    const response = await fetch(`${API_BASE_URL}/api/v1/kb/context?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to get context: ${response.statusText}`);
    }
    return response.json();
  }
}

export const knowledgeBaseApi = new KnowledgeBaseApi();
