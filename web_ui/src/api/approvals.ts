import { apiClient } from './client';

export interface ApprovalRequest {
  id: string;
  tool_call_id: string;
  session_id: string;
  thread_id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  message: string;
  impact_summary?: string;
  status: 'pending' | 'approved' | 'rejected' | 'expired' | 'cancelled';
  created_at: string;
  expires_at?: string;
  resolved_at?: string;
  resolved_by?: string;
  rejection_reason?: string;
}

export interface ApprovalListResponse {
  approvals: ApprovalRequest[];
  total: number;
}

export interface ApproveRequest {
  reason?: string;
}

export interface RejectRequest {
  reason?: string;
}

export interface ApprovalResponse {
  approval_id: string;
  status: 'approved' | 'rejected' | 'cancelled';
  message: string;
}

export const approvalsApi = {
  /**
   * List pending approvals for a session
   */
  async listPending(sessionId: string): Promise<ApprovalListResponse> {
    const { data } = await apiClient.get<ApprovalListResponse>('/api/v1/approvals/pending', {
      params: { session_id: sessionId },
    });
    return data;
  },

  /**
   * Get a specific approval request
   */
  async get(approvalId: string): Promise<ApprovalRequest> {
    const { data } = await apiClient.get<ApprovalRequest>(`/api/v1/approvals/${approvalId}`);
    return data;
  },

  /**
   * Approve a pending request
   */
  async approve(approvalId: string, request?: ApproveRequest): Promise<ApprovalResponse> {
    const { data } = await apiClient.post<ApprovalResponse>(
      `/api/v1/approvals/${approvalId}/approve`,
      request || {}
    );
    return data;
  },

  /**
   * Reject a pending request
   */
  async reject(approvalId: string, request?: RejectRequest): Promise<ApprovalResponse> {
    const { data } = await apiClient.post<ApprovalResponse>(
      `/api/v1/approvals/${approvalId}/reject`,
      request || {}
    );
    return data;
  },

  /**
   * Cancel a pending request
   */
  async cancel(approvalId: string): Promise<ApprovalResponse> {
    const { data } = await apiClient.post<ApprovalResponse>(
      `/api/v1/approvals/${approvalId}/cancel`
    );
    return data;
  },
};
