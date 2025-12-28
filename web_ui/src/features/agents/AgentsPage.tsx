import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, MessageSquare, Pencil, Trash2, Bot, Cpu, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { agentsApi } from '@/api';
import type { AgentInfo, CustomAgentInfo } from '@/types/api';
import { cn } from '@/lib/cn';

// Generate a consistent color from agent name
function getAvatarColor(name: string): string {
  const colors = [
    'bg-violet-500',
    'bg-blue-500',
    'bg-cyan-500',
    'bg-teal-500',
    'bg-green-500',
    'bg-amber-500',
    'bg-orange-500',
    'bg-rose-500',
    'bg-pink-500',
    'bg-indigo-500',
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

// Get initials from agent name
function getInitials(name: string): string {
  return name
    .split(/[_\s-]+/)
    .map((word) => word[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

interface AgentCardProps {
  name: string;
  description: string;
  tools: string[];
  type: 'builtin' | 'custom';
  agentId?: string;
  onChat?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
}

function AgentCard({ name, description, tools, type, onChat, onEdit, onDelete }: AgentCardProps) {
  const initials = getInitials(name);
  const avatarColor = getAvatarColor(name);

  return (
    <Card className="group relative overflow-hidden transition-all hover:shadow-lg hover:border-primary/50">
      <CardContent className="p-6">
        <div className="flex items-start gap-4">
          {/* Avatar */}
          <div
            className={cn(
              'flex h-12 w-12 shrink-0 items-center justify-center rounded-lg text-white font-semibold',
              avatarColor
            )}
          >
            {initials}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-lg truncate">{name.replace(/_/g, ' ')}</h3>
              <Badge variant={type === 'builtin' ? 'secondary' : 'outline'} className="shrink-0">
                {type === 'builtin' ? (
                  <>
                    <Cpu className="h-3 w-3 mr-1" />
                    Built-in
                  </>
                ) : (
                  <>
                    <Bot className="h-3 w-3 mr-1" />
                    Custom
                  </>
                )}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground line-clamp-2 mb-3">{description}</p>

            {/* Tools */}
            <div className="flex flex-wrap gap-1">
              {tools.slice(0, 4).map((tool) => (
                <Badge key={tool} variant="outline" className="text-xs">
                  {tool}
                </Badge>
              ))}
              {tools.length > 4 && (
                <Badge variant="outline" className="text-xs">
                  +{tools.length - 4} more
                </Badge>
              )}
            </div>
          </div>
        </div>

        {/* Action buttons */}
        <div className="absolute top-4 right-4 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {onChat && (
            <Button variant="ghost" size="icon" onClick={onChat} title="Chat with agent">
              <MessageSquare className="h-4 w-4" />
            </Button>
          )}
          {onEdit && (
            <Button variant="ghost" size="icon" onClick={onEdit} title="Edit agent">
              <Pencil className="h-4 w-4" />
            </Button>
          )}
          {onDelete && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onDelete}
              title="Delete agent"
              className="text-destructive hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function AgentsPage() {
  const navigate = useNavigate();
  const [builtinAgents, setBuiltinAgents] = useState<AgentInfo[]>([]);
  const [customAgents, setCustomAgents] = useState<CustomAgentInfo[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    setIsLoading(true);
    try {
      const [builtin, custom] = await Promise.all([
        agentsApi.listBuiltin(),
        agentsApi.listCustomAgents(),
      ]);
      setBuiltinAgents(builtin);
      setCustomAgents(custom);
    } catch (error) {
      console.error('Failed to load agents:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (agentId: string) => {
    if (deleteConfirm === agentId) {
      try {
        await agentsApi.deleteCustomAgent(agentId);
        setCustomAgents((prev) => prev.filter((a) => a.id !== agentId));
        setDeleteConfirm(null);
      } catch (error) {
        console.error('Failed to delete agent:', error);
      }
    } else {
      setDeleteConfirm(agentId);
      // Auto-reset after 3 seconds
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  };

  const handleChatWithAgent = (agentName: string) => {
    // Navigate to multi-agent page with this agent selected
    navigate(`/multi-agent?agent=${agentName}`);
  };

  const filteredBuiltin = builtinAgents.filter(
    (a) =>
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredCustom = customAgents.filter(
    (a) =>
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (a.description && a.description.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const allAgents = [
    ...filteredBuiltin.map((a) => ({ ...a, type: 'builtin' as const })),
    ...filteredCustom.map((a) => ({
      name: a.name,
      description: a.description || 'Custom agent',
      tools: a.tools || [],
      type: 'custom' as const,
      id: a.id,
    })),
  ];

  return (
    <div className="container py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Agents</h1>
          <p className="text-muted-foreground mt-1">
            Manage your built-in and custom AI agents
          </p>
        </div>
        <Button onClick={() => navigate('/builder')} className="gap-2">
          <Plus className="h-4 w-4" />
          New Agent
        </Button>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search agents by name..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Tabs */}
      <Tabs defaultValue="all" className="space-y-6">
        <TabsList>
          <TabsTrigger value="all">
            All Agents ({allAgents.length})
          </TabsTrigger>
          <TabsTrigger value="builtin">
            Built-in ({filteredBuiltin.length})
          </TabsTrigger>
          <TabsTrigger value="custom">
            Custom ({filteredCustom.length})
          </TabsTrigger>
        </TabsList>

        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Card key={i} className="animate-pulse">
                <CardContent className="p-6">
                  <div className="flex items-start gap-4">
                    <div className="h-12 w-12 rounded-lg bg-muted" />
                    <div className="flex-1 space-y-2">
                      <div className="h-5 bg-muted rounded w-2/3" />
                      <div className="h-4 bg-muted rounded w-full" />
                      <div className="h-4 bg-muted rounded w-1/2" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <>
            <TabsContent value="all" className="space-y-4">
              {allAgents.length === 0 ? (
                <Card>
                  <CardContent className="py-12 text-center">
                    <Bot className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                    <h3 className="text-lg font-medium mb-2">No agents found</h3>
                    <p className="text-muted-foreground mb-4">
                      {searchQuery
                        ? 'Try a different search term'
                        : 'Create your first custom agent to get started'}
                    </p>
                    {!searchQuery && (
                      <Button onClick={() => navigate('/builder')}>
                        <Plus className="h-4 w-4 mr-2" />
                        Create Agent
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {allAgents.map((agent) => (
                    <AgentCard
                      key={agent.type === 'custom' ? agent.id : agent.name}
                      name={agent.name}
                      description={agent.description}
                      tools={agent.tools}
                      type={agent.type}
                      onChat={() => handleChatWithAgent(agent.name)}
                      onEdit={
                        agent.type === 'custom'
                          ? () => navigate(`/builder/${agent.id}`)
                          : undefined
                      }
                      onDelete={
                        agent.type === 'custom'
                          ? () => handleDelete(agent.id!)
                          : undefined
                      }
                    />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="builtin" className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredBuiltin.map((agent) => (
                  <AgentCard
                    key={agent.name}
                    name={agent.name}
                    description={agent.description}
                    tools={agent.tools}
                    type="builtin"
                    onChat={() => handleChatWithAgent(agent.name)}
                  />
                ))}
              </div>
            </TabsContent>

            <TabsContent value="custom" className="space-y-4">
              {filteredCustom.length === 0 ? (
                <Card>
                  <CardContent className="py-12 text-center">
                    <Bot className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                    <h3 className="text-lg font-medium mb-2">No custom agents yet</h3>
                    <p className="text-muted-foreground mb-4">
                      Create your first custom agent with your own tools and instructions
                    </p>
                    <Button onClick={() => navigate('/builder')}>
                      <Plus className="h-4 w-4 mr-2" />
                      Create Agent
                    </Button>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {filteredCustom.map((agent) => (
                    <AgentCard
                      key={agent.id}
                      name={agent.name}
                      description={agent.description || 'Custom agent'}
                      tools={agent.tools || []}
                      type="custom"
                      agentId={agent.id}
                      onChat={() => handleChatWithAgent(agent.name)}
                      onEdit={() => navigate(`/builder/${agent.id}`)}
                      onDelete={() => handleDelete(agent.id)}
                    />
                  ))}
                </div>
              )}
            </TabsContent>
          </>
        )}
      </Tabs>

      {/* Delete confirmation toast */}
      {deleteConfirm && (
        <div className="fixed bottom-4 right-4 bg-destructive text-destructive-foreground px-4 py-3 rounded-lg shadow-lg flex items-center gap-3">
          <span>Click delete again to confirm</span>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setDeleteConfirm(null)}
          >
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}
