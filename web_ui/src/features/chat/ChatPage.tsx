import { useEffect, useRef, useState, useCallback } from 'react';
import { Send, Loader2, Wrench } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useSessionStore, useSettingsStore } from '@/stores';
import { useMCPStore } from '@/stores/mcpStore';
import { chatApi, sessionsApi } from '@/api';
import type { Message, SessionSummary } from '@/types/api';
import { cn } from '@/lib/cn';
import { ThreadList } from './ThreadList';
import { MCPServerToggle } from './MCPServerToggle';
import { ApprovalCard, ChatSettingsBar, ChatSettingsPanel, ImageUpload, ImagePreviewGrid } from '@/components/chat';
import type { ApprovalRequestEvent } from '@/components/chat';
import { useImageUpload } from '@/hooks/useImageUpload';

export function ChatPage() {
  const [input, setInput] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [showMCPPanel, setShowMCPPanel] = useState(false);
  const [threads, setThreads] = useState<SessionSummary[]>([]);
  const [isLoadingThreads, setIsLoadingThreads] = useState(true);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [toolActivity, setToolActivity] = useState<{ name: string; status: 'calling' | 'done' } | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequestEvent[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Use the shared image upload hook
  const {
    selectedImages,
    fileInputRef,
    handleImageSelect,
    handleRemoveImage,
    handlePaste,
    clearImages,
  } = useImageUpload();

  // MCP store
  const { getEnabledServers } = useMCPStore();

  const {
    sessionId,
    messages,
    isLoading,
    isStreaming,
    streamingContent,
    error,
    setSessionId,
    addMessage,
    setMessages,
    setStreaming,
    setError,
    appendStreamingContent,
    clearStreamingContent,
  } = useSessionStore();

  const { provider, model, temperature } = useSettingsStore();

  // Fetch thread history
  const loadThreads = useCallback(async () => {
    setIsLoadingThreads(true);
    try {
      const result = await sessionsApi.list(50, 0);
      setThreads(result.sessions);
    } catch (err) {
      console.error('Failed to load threads:', err);
    } finally {
      setIsLoadingThreads(false);
    }
  }, []);

  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  // Initialize session if none exists
  useEffect(() => {
    if (!sessionId && !isLoadingThreads && threads.length === 0) {
      handleNewThread();
    }
  }, [sessionId, isLoadingThreads, threads.length]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingContent]);

  // Create new thread
  const handleNewThread = async () => {
    try {
      const session = await sessionsApi.create({ metadata: { source: 'web_ui' } });
      setSessionId(session.session_id);
      setMessages([]);
      clearStreamingContent();
      setError(null);
      // Refresh thread list
      loadThreads();
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  // Switch to existing thread
  const handleSelectThread = async (selectedSessionId: string) => {
    if (selectedSessionId === sessionId) return;

    try {
      const session = await sessionsApi.get(selectedSessionId);
      setSessionId(session.session_id);
      setMessages(session.messages);
      clearStreamingContent();
      setError(null);
    } catch (err) {
      console.error('Failed to load session:', err);
      setError('Failed to load conversation');
    }
  };

  // Delete thread
  const handleDeleteThread = async (deleteSessionId: string) => {
    try {
      await sessionsApi.delete(deleteSessionId);
      // Remove from local state
      setThreads((prev) => prev.filter((t) => t.session_id !== deleteSessionId));

      // If we deleted the current session, create a new one
      if (deleteSessionId === sessionId) {
        const remainingThreads = threads.filter((t) => t.session_id !== deleteSessionId);
        if (remainingThreads.length > 0) {
          handleSelectThread(remainingThreads[0].session_id);
        } else {
          handleNewThread();
        }
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading || isStreaming) return;

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
      images: selectedImages.length > 0 ? [...selectedImages] : undefined,
      timestamp: new Date().toISOString(),
    };

    addMessage(userMessage);
    setInput('');
    clearImages(); // Clear images after adding to message
    setError(null);
    setStreaming(true);
    clearStreamingContent();
    setToolActivity(null);

    // Get enabled MCP servers
    const mcpServers = getEnabledServers();

    try {
      for await (const event of chatApi.streamMessage({
        message: userMessage.content,
        images: userMessage.images,
        session_id: sessionId,
        provider,
        model,
        temperature,
        mcp_servers: mcpServers.length > 0 ? mcpServers : null,
      })) {
        if (event.event === 'start') {
          if (event.session_id && !sessionId) {
            setSessionId(event.session_id);
          }
        } else if (event.event === 'token') {
          appendStreamingContent(event.content || '');
        } else if (event.event === 'tool_call') {
          // Show tool call activity
          setToolActivity({ name: event.tool_name || 'Unknown', status: 'calling' });
        } else if (event.event === 'tool_result') {
          // Tool completed
          setToolActivity({ name: event.tool_name || 'Unknown', status: 'done' });
          // Clear after a short delay
          setTimeout(() => setToolActivity(null), 1500);
        } else if (event.event === 'approval_request') {
          // HITL approval required - clear tool activity since it's now pending approval
          setToolActivity(null);
          const approvalRequest: ApprovalRequestEvent = {
            approval_id: event.approval_id || '',
            tool_name: event.tool_name || 'unknown',
            tool_id: event.tool_id || '',
            message: typeof event.message === 'string' ? event.message : 'Approve this action?',
            tool_args: event.tool_args || {},
            expires_at: event.expires_at,
            config: {
              show_args: event.config?.show_args ?? true,
              timeout_seconds: event.config?.timeout_seconds ?? 300,
              require_reason_on_reject: event.config?.require_reason_on_reject ?? false,
            },
          };
          setPendingApprovals((prev) => [...prev, approvalRequest]);
        } else if (event.event === 'done') {
          if (event.message) {
            addMessage(event.message);
          }
          clearStreamingContent();
          setStreaming(false);
          setToolActivity(null);
          // Refresh thread list to update last message
          loadThreads();
        } else if (event.event === 'error') {
          setError(event.error || 'An error occurred');
          setStreaming(false);
          setToolActivity(null);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
      setStreaming(false);
      setToolActivity(null);
    }
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* Thread Sidebar */}
      <ThreadList
        threads={threads}
        currentSessionId={sessionId}
        isCollapsed={isSidebarCollapsed}
        onSelectThread={handleSelectThread}
        onNewThread={handleNewThread}
        onDeleteThread={handleDeleteThread}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 flex flex-col p-4 overflow-hidden">
          {/* Settings Bar */}
          <div className="mb-4 shrink-0">
            <ChatSettingsBar
              showSettings={showSettings}
              onToggleSettings={() => setShowSettings(!showSettings)}
            />
          </div>

          {/* Settings Panel */}
          {showSettings && (
            <ChatSettingsPanel className="mb-4 shrink-0" />
          )}

          {/* MCP Servers Panel */}
          {showSettings && (
            <div className="mb-4 shrink-0">
              <MCPServerToggle
                isOpen={showMCPPanel}
                onToggle={() => setShowMCPPanel(!showMCPPanel)}
              />
            </div>
          )}

          {/* Messages */}
          <ScrollArea className="flex-1" ref={scrollRef}>
            <div className="space-y-4 pb-4 pr-4">
              {messages.length === 0 && !isStreaming && (
                <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                  <div className="text-center">
                    <p className="mb-2">Start a conversation by sending a message below.</p>
                    <p className="text-sm">Your chat history will appear in the sidebar.</p>
                  </div>
                </div>
              )}

              {messages.map((message, index) => (
                <div
                  key={index}
                  className={cn(
                    'flex',
                    message.role === 'user' ? 'justify-end' : 'justify-start'
                  )}
                >
                  <div
                    className={cn(
                      'max-w-[80%] rounded-lg px-4 py-2',
                      message.role === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted'
                    )}
                  >
                    {/* Display images if present */}
                    {message.images && message.images.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-2">
                        {message.images.map((img, imgIdx) => (
                          <img
                            key={imgIdx}
                            src={img}
                            alt={`Uploaded image ${imgIdx + 1}`}
                            className="max-h-48 rounded cursor-pointer hover:opacity-90 transition-opacity"
                            onClick={() => window.open(img, '_blank')}
                          />
                        ))}
                      </div>
                    )}
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  </div>
                </div>
              ))}

              {isStreaming && (
                <div className="flex justify-start">
                  <div className="max-w-[80%] rounded-lg bg-muted px-4 py-2">
                    {toolActivity && (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                        <Wrench className="h-3 w-3" />
                        <span>
                          {toolActivity.status === 'calling'
                            ? `Calling ${toolActivity.name}...`
                            : `${toolActivity.name} completed`}
                        </span>
                        {toolActivity.status === 'calling' && (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        )}
                      </div>
                    )}
                    {streamingContent && (
                      <p className="whitespace-pre-wrap">{streamingContent}</p>
                    )}
                    {!toolActivity && !streamingContent && (
                      <span className="inline-block text-muted-foreground">Thinking...</span>
                    )}
                    <span className="inline-block h-4 w-1 animate-pulse bg-foreground" />
                  </div>
                </div>
              )}

              {error && (
                <div className="flex justify-center">
                  <div className="rounded-lg bg-destructive/10 px-4 py-2 text-destructive">
                    {error}
                  </div>
                </div>
              )}

              {/* Pending Approval Requests */}
              {pendingApprovals.map((approval) => (
                <div key={approval.approval_id} className="flex justify-center">
                  <ApprovalCard
                    request={approval}
                    onResolved={() => {
                      // Remove from pending list when resolved
                      setPendingApprovals((prev) =>
                        prev.filter((a) => a.approval_id !== approval.approval_id)
                      );
                    }}
                    className="max-w-[80%]"
                  />
                </div>
              ))}
            </div>
          </ScrollArea>

          {/* Input */}
          <div className="mt-4 shrink-0">
            {/* Image Preview */}
            <ImagePreviewGrid
              images={selectedImages}
              onRemove={handleRemoveImage}
              className="mb-2"
            />

            <form onSubmit={handleSubmit} className="flex gap-2">
              {/* Image upload button */}
              <ImageUpload
                selectedImages={selectedImages}
                fileInputRef={fileInputRef}
                onImageSelect={handleImageSelect}
                onImageRemove={handleRemoveImage}
                onOpenFileDialog={() => fileInputRef.current?.click()}
                disabled={isLoading || isStreaming}
              />

              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPaste={handlePaste}
                placeholder="Type a message or paste an image..."
                disabled={isLoading || isStreaming}
                className="flex-1"
              />
              <Button type="submit" disabled={isLoading || isStreaming || !input.trim()}>
                {isLoading || isStreaming ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
