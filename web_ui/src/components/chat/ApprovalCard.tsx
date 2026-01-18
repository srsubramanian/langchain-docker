import { useState } from 'react';
import { Check, X, Clock, AlertTriangle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { approvalsApi } from '@/api';
import { cn } from '@/lib/cn';

export interface ApprovalRequestEvent {
  approval_id: string;
  tool_name: string;
  tool_id: string;
  message: string;
  tool_args?: Record<string, unknown>;
  expires_at?: string;
  config: {
    show_args: boolean;
    timeout_seconds: number;
    require_reason_on_reject: boolean;
  };
}

interface ApprovalCardProps {
  request: ApprovalRequestEvent;
  onResolved?: (status: 'approved' | 'rejected') => void;
  className?: string;
}

export function ApprovalCard({ request, onResolved, className }: ApprovalCardProps) {
  const [status, setStatus] = useState<'pending' | 'approved' | 'rejected' | 'loading'>('pending');
  const [rejectionReason, setRejectionReason] = useState('');
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApprove = async () => {
    setStatus('loading');
    setError(null);
    try {
      await approvalsApi.approve(request.approval_id);
      setStatus('approved');
      onResolved?.('approved');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve');
      setStatus('pending');
    }
  };

  const handleReject = async () => {
    if (request.config.require_reason_on_reject && !rejectionReason.trim()) {
      setError('Please provide a reason for rejection');
      return;
    }

    setStatus('loading');
    setError(null);
    try {
      await approvalsApi.reject(request.approval_id, {
        reason: rejectionReason.trim() || undefined,
      });
      setStatus('rejected');
      onResolved?.('rejected');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject');
      setStatus('pending');
    }
  };

  const formatTimeRemaining = () => {
    if (!request.expires_at) return null;
    const expires = new Date(request.expires_at);
    const now = new Date();
    const diffMs = expires.getTime() - now.getTime();
    if (diffMs <= 0) return 'Expired';
    const diffSecs = Math.floor(diffMs / 1000);
    const mins = Math.floor(diffSecs / 60);
    const secs = diffSecs % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const isResolved = status === 'approved' || status === 'rejected';
  const isLoading = status === 'loading';

  return (
    <Card className={cn(
      'w-full border-2',
      status === 'pending' && 'border-yellow-500/50 bg-yellow-500/5',
      status === 'approved' && 'border-green-500/50 bg-green-500/5',
      status === 'rejected' && 'border-red-500/50 bg-red-500/5',
      isLoading && 'opacity-75',
      className
    )}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
            Approval Required
          </CardTitle>
          <div className="flex items-center gap-2">
            {request.expires_at && status === 'pending' && (
              <Badge variant="outline" className="text-xs">
                <Clock className="h-3 w-3 mr-1" />
                {formatTimeRemaining()}
              </Badge>
            )}
            <Badge variant={
              status === 'approved' ? 'default' :
              status === 'rejected' ? 'destructive' :
              'secondary'
            }>
              {status === 'pending' ? 'Pending' :
               status === 'approved' ? 'Approved' :
               status === 'rejected' ? 'Rejected' : 'Processing'}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm">{request.message}</p>

        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            Tool: {request.tool_name}
          </Badge>
        </div>

        {request.config.show_args && request.tool_args && (
          <div className="bg-muted rounded-md p-2">
            <p className="text-xs text-muted-foreground mb-1">Arguments:</p>
            <pre className="text-xs overflow-x-auto">
              {JSON.stringify(request.tool_args, null, 2)}
            </pre>
          </div>
        )}

        {showRejectInput && status === 'pending' && (
          <Textarea
            placeholder={request.config.require_reason_on_reject
              ? 'Reason for rejection (required)'
              : 'Reason for rejection (optional)'
            }
            value={rejectionReason}
            onChange={(e) => setRejectionReason(e.target.value)}
            className="text-sm"
            rows={2}
          />
        )}

        {error && (
          <p className="text-xs text-red-500">{error}</p>
        )}
      </CardContent>

      {!isResolved && (
        <CardFooter className="pt-0">
          {!showRejectInput ? (
            <div className="flex gap-2 w-full">
              <Button
                size="sm"
                variant="default"
                className="flex-1 bg-green-600 hover:bg-green-700"
                onClick={handleApprove}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    <Check className="h-4 w-4 mr-1" />
                    Approve
                  </>
                )}
              </Button>
              <Button
                size="sm"
                variant="destructive"
                className="flex-1"
                onClick={() => setShowRejectInput(true)}
                disabled={isLoading}
              >
                <X className="h-4 w-4 mr-1" />
                Reject
              </Button>
            </div>
          ) : (
            <div className="flex gap-2 w-full">
              <Button
                size="sm"
                variant="outline"
                className="flex-1"
                onClick={() => {
                  setShowRejectInput(false);
                  setRejectionReason('');
                  setError(null);
                }}
                disabled={isLoading}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                variant="destructive"
                className="flex-1"
                onClick={handleReject}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  'Confirm Reject'
                )}
              </Button>
            </div>
          )}
        </CardFooter>
      )}

      {isResolved && (
        <CardFooter className="pt-0">
          <div className="flex items-center gap-2 w-full justify-center text-sm">
            {status === 'approved' ? (
              <>
                <Check className="h-4 w-4 text-green-500" />
                <span className="text-green-600">Action approved</span>
              </>
            ) : (
              <>
                <X className="h-4 w-4 text-red-500" />
                <span className="text-red-600">Action rejected</span>
              </>
            )}
          </div>
        </CardFooter>
      )}
    </Card>
  );
}
