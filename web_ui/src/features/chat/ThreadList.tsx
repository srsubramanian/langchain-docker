import { useState } from 'react';
import { MessageSquare, Plus, Trash2, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/cn';
import type { SessionSummary } from '@/types/api';

interface ThreadListProps {
  threads: SessionSummary[];
  currentSessionId: string | null;
  isCollapsed: boolean;
  onSelectThread: (sessionId: string) => void;
  onNewThread: () => void;
  onDeleteThread: (sessionId: string) => void;
  onToggleCollapse: () => void;
}

// Format relative time
function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

// Get preview text from last message
function getPreviewText(lastMessage: string | null | undefined, maxLength = 50): string {
  if (!lastMessage) return 'No messages yet';
  if (lastMessage.length <= maxLength) return lastMessage;
  return lastMessage.substring(0, maxLength) + '...';
}

export function ThreadList({
  threads,
  currentSessionId,
  isCollapsed,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  onToggleCollapse,
}: ThreadListProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const filteredThreads = threads.filter((thread) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      thread.last_message?.toLowerCase().includes(query) ||
      thread.session_id.toLowerCase().includes(query)
    );
  });

  const handleDelete = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (deleteConfirm === sessionId) {
      onDeleteThread(sessionId);
      setDeleteConfirm(null);
    } else {
      setDeleteConfirm(sessionId);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  };

  if (isCollapsed) {
    return (
      <div className="flex flex-col items-center py-4 border-r bg-muted/30 w-12">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleCollapse}
          className="mb-4"
          title="Expand sidebar"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onNewThread}
          title="New chat"
        >
          <Plus className="h-4 w-4" />
        </Button>
        <div className="flex-1" />
        <div className="text-xs text-muted-foreground rotate-90 whitespace-nowrap">
          {threads.length} threads
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col w-72 border-r bg-muted/30">
      {/* Header */}
      <div className="p-3 border-b flex items-center justify-between">
        <h2 className="font-semibold text-sm">Chat History</h2>
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleCollapse}
          title="Collapse sidebar"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <Button onClick={onNewThread} className="w-full gap-2" size="sm">
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>

      {/* Search */}
      <div className="px-3 pb-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search threads..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 h-8 text-sm"
          />
        </div>
      </div>

      {/* Thread List */}
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {filteredThreads.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm">
              {searchQuery ? 'No threads found' : 'No chat history yet'}
            </div>
          ) : (
            filteredThreads.map((thread) => (
              <div
                key={thread.session_id}
                onClick={() => onSelectThread(thread.session_id)}
                className={cn(
                  'group relative p-3 rounded-lg cursor-pointer transition-colors',
                  thread.session_id === currentSessionId
                    ? 'bg-primary/10 border border-primary/20'
                    : 'hover:bg-muted'
                )}
              >
                <div className="flex items-start gap-2">
                  <MessageSquare className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      {getPreviewText(thread.last_message, 30)}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-muted-foreground">
                        {formatRelativeTime(thread.updated_at)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {thread.message_count} msgs
                      </span>
                    </div>
                  </div>
                </div>

                {/* Delete button on hover */}
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn(
                    'absolute top-2 right-2 h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity',
                    deleteConfirm === thread.session_id && 'opacity-100 text-destructive'
                  )}
                  onClick={(e) => handleDelete(e, thread.session_id)}
                  title={deleteConfirm === thread.session_id ? 'Click again to confirm' : 'Delete thread'}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))
          )}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="p-3 border-t text-xs text-muted-foreground text-center">
        {threads.length} {threads.length === 1 ? 'thread' : 'threads'}
      </div>
    </div>
  );
}
