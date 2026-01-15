import { useEffect } from 'react';
import { Plug, Check, Loader2, AlertCircle, ChevronDown } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useMCPStore } from '@/stores/mcpStore';
import { cn } from '@/lib/cn';

interface MCPServerToggleProps {
  isOpen: boolean;
  onToggle: () => void;
}

export function MCPServerToggle({ isOpen, onToggle }: MCPServerToggleProps) {
  const {
    servers,
    enabledServerIds,
    loading,
    error,
    fetchServers,
    toggleServer,
    startServer,
  } = useMCPStore();

  // Fetch servers on mount
  useEffect(() => {
    fetchServers();
  }, [fetchServers]);

  const enabledCount = enabledServerIds.filter((id) =>
    servers.some((s) => s.id === id)
  ).length;

  const handleServerClick = async (serverId: string) => {
    const server = servers.find((s) => s.id === serverId);
    if (!server) return;

    // If enabling and server is stopped, start it first
    if (!enabledServerIds.includes(serverId) && server.status === 'stopped') {
      await startServer(serverId);
    }

    toggleServer(serverId);
  };

  return (
    <Card className="border-dashed">
      <CardHeader
        className="cursor-pointer py-3 hover:bg-accent/50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Plug className="h-4 w-4" />
            <CardTitle className="text-sm font-medium">MCP Servers</CardTitle>
            {enabledCount > 0 && (
              <Badge variant="secondary" className="text-xs">
                {enabledCount} enabled
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            <ChevronDown
              className={cn(
                'h-4 w-4 text-muted-foreground transition-transform duration-200',
                isOpen && 'rotate-180'
              )}
            />
          </div>
        </div>
      </CardHeader>

      {isOpen && (
        <CardContent className="pt-0">
          {error && (
            <div className="flex items-center gap-2 text-sm text-destructive mb-3">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}

          {servers.length === 0 && !loading && (
            <p className="text-sm text-muted-foreground">
              No MCP servers configured.
            </p>
          )}

          <div className="space-y-2">
            {servers.map((server) => {
              const isEnabled = enabledServerIds.includes(server.id);
              const isRunning = server.status === 'running';

              return (
                <Button
                  key={server.id}
                  variant={isEnabled ? 'secondary' : 'outline'}
                  size="sm"
                  className={cn(
                    'w-full justify-start gap-2 h-auto py-2',
                    isEnabled && 'ring-1 ring-primary'
                  )}
                  onClick={() => handleServerClick(server.id)}
                  disabled={loading || !server.enabled}
                >
                  {/* Status indicator */}
                  <span
                    className={cn(
                      'h-2 w-2 rounded-full shrink-0',
                      isRunning ? 'bg-green-500' : 'bg-gray-400'
                    )}
                  />

                  {/* Server info */}
                  <div className="flex flex-col items-start text-left flex-1 min-w-0">
                    <span className="font-medium truncate w-full">
                      {server.name}
                    </span>
                    <span className="text-xs text-muted-foreground truncate w-full">
                      {server.description}
                    </span>
                  </div>

                  {/* Tool count badge */}
                  {server.tools && server.tools.length > 0 && (
                    <Badge variant="outline" className="text-xs shrink-0">
                      {server.tools.length} tools
                    </Badge>
                  )}

                  {/* Enabled check */}
                  {isEnabled && (
                    <Check className="h-4 w-4 text-primary shrink-0" />
                  )}
                </Button>
              );
            })}
          </div>

          {servers.length > 0 && (
            <p className="text-xs text-muted-foreground mt-3">
              Click to toggle. Enabled servers provide tools for the chat.
            </p>
          )}
        </CardContent>
      )}
    </Card>
  );
}
