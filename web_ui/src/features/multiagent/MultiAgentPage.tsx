import { useEffect, useMemo, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import ReactFlow, {
  type Node,
  type Edge,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Send, Loader2, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { agentsApi, modelsApi } from '@/api';
import { useSettingsStore } from '@/stores';
import type { WorkflowInvokeResponse, ProviderInfo, ModelInfo } from '@/types/api';
import { cn } from '@/lib/cn';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const AGENT_PRESETS: Record<string, string[]> = {
  all: ['math_expert', 'weather_expert', 'research_expert', 'finance_expert'],
  math_weather: ['math_expert', 'weather_expert'],
  research_finance: ['research_expert', 'finance_expert'],
  math_only: ['math_expert'],
};

function generateWorkflowGraph(agents: string[]): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Start node
  nodes.push({
    id: 'start',
    type: 'input',
    position: { x: 250, y: 0 },
    data: { label: 'User Input' },
    style: { background: '#1e293b', color: '#fff', border: '1px solid #334155' },
  });

  // Supervisor node
  nodes.push({
    id: 'supervisor',
    position: { x: 225, y: 100 },
    data: { label: 'Supervisor' },
    style: { background: '#14b8a6', color: '#fff', border: 'none', fontWeight: 'bold' },
  });

  edges.push({
    id: 'start-supervisor',
    source: 'start',
    target: 'supervisor',
    animated: true,
    markerEnd: { type: MarkerType.ArrowClosed },
  });

  // Agent nodes
  const agentCount = agents.length;
  const spacing = 150;
  const startX = 250 - ((agentCount - 1) * spacing) / 2;

  agents.forEach((agent, index) => {
    const nodeId = agent;
    nodes.push({
      id: nodeId,
      position: { x: startX + index * spacing, y: 220 },
      data: { label: agent.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase()) },
      style: { background: '#1e293b', color: '#fff', border: '1px solid #334155' },
    });

    edges.push({
      id: `supervisor-${nodeId}`,
      source: 'supervisor',
      target: nodeId,
      markerEnd: { type: MarkerType.ArrowClosed },
    });

    edges.push({
      id: `${nodeId}-supervisor`,
      source: nodeId,
      target: 'supervisor',
      style: { strokeDasharray: '5,5' },
    });
  });

  // End node
  nodes.push({
    id: 'end',
    type: 'output',
    position: { x: 250, y: 340 },
    data: { label: 'Response' },
    style: { background: '#1e293b', color: '#fff', border: '1px solid #334155' },
  });

  edges.push({
    id: 'supervisor-end',
    source: 'supervisor',
    target: 'end',
    markerEnd: { type: MarkerType.ArrowClosed },
  });

  return { nodes, edges };
}

// Generate avatar color from agent name
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

export function MultiAgentPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [input, setInput] = useState('');
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null); // For session persistence
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState<WorkflowInvokeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);

  const { provider, model, agentPreset, setAgentPreset, setProvider, setModel } = useSettingsStore();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);

  // Check if we're in single-agent mode (from ?agent= query param)
  const singleAgentName = searchParams.get('agent');
  const isSingleAgentMode = !!singleAgentName;

  // Determine which agents to use - memoize to prevent unnecessary effect reruns
  const selectedAgents = useMemo(
    () =>
      isSingleAgentMode
        ? [singleAgentName!]
        : (AGENT_PRESETS[agentPreset] || AGENT_PRESETS.all),
    [isSingleAgentMode, singleAgentName, agentPreset]
  );

  const { nodes: initialNodes, edges: initialEdges } = generateWorkflowGraph(
    isSingleAgentMode ? [] : selectedAgents // Don't show graph in single-agent mode
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update graph when preset changes (only in multi-agent mode)
  useEffect(() => {
    if (!isSingleAgentMode) {
      const { nodes: newNodes, edges: newEdges } = generateWorkflowGraph(selectedAgents);
      setNodes(newNodes);
      setEdges(newEdges);
    }
  }, [agentPreset, selectedAgents, setNodes, setEdges, isSingleAgentMode]);

  // Create workflow when agents change
  useEffect(() => {
    let currentWorkflowId: string | null = null;
    let isCancelled = false;

    // Clear conversation state when switching workflows/presets
    setSessionId(null);
    setMessages([]);
    setResponse(null);
    setError(null);

    if (selectedAgents.length > 0) {
      agentsApi
        .createWorkflow({
          agents: selectedAgents,
          provider,
        })
        .then((result) => {
          if (!isCancelled) {
            currentWorkflowId = result.workflow_id;
            setWorkflowId(result.workflow_id);
          } else {
            // Effect was cancelled, clean up the workflow we just created
            agentsApi.deleteWorkflow(result.workflow_id).catch(console.error);
          }
        })
        .catch((err) => {
          if (!isCancelled) {
            console.error('Failed to create workflow:', err);
          }
        });
    }

    return () => {
      isCancelled = true;
      if (currentWorkflowId) {
        agentsApi.deleteWorkflow(currentWorkflowId).catch(console.error);
      }
    };
  }, [selectedAgents, provider]);

  // Fetch providers on mount (for single-agent mode)
  useEffect(() => {
    if (isSingleAgentMode) {
      modelsApi.listProviders().then(setProviders).catch(console.error);
    }
  }, [isSingleAgentMode]);

  // Fetch available models when provider changes (for single-agent mode)
  useEffect(() => {
    if (isSingleAgentMode && provider) {
      modelsApi
        .getProviderDetails(provider)
        .then((details) => {
          setAvailableModels(details.available_models);
        })
        .catch(console.error);
    }
  }, [isSingleAgentMode, provider]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading || !workflowId) return;

    const userMessage = input.trim();
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setInput('');
    setIsLoading(true);
    setError(null);

    try {
      const result = await agentsApi.invokeWorkflow(workflowId, {
        message: userMessage,
        session_id: sessionId, // Pass session ID for conversation continuity
      });
      setResponse(result);
      setSessionId(result.session_id); // Store session ID for subsequent requests
      setMessages((prev) => [...prev, { role: 'assistant', content: result.response }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Workflow execution failed');
    } finally {
      setIsLoading(false);
    }
  };

  // Single-agent mode: Full-width chat UI
  if (isSingleAgentMode) {
    const agentDisplayName = singleAgentName.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    const avatarColor = getAvatarColor(singleAgentName);
    const initials = getInitials(singleAgentName);

    return (
      <div className="flex h-[calc(100vh-3.5rem)] flex-col">
        {/* Header with agent info */}
        <div className="border-b bg-card px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => navigate('/agents')}
                title="Back to agents"
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <div
                className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-lg text-white font-semibold',
                  avatarColor
                )}
              >
                {initials}
              </div>
              <div>
                <h1 className="text-xl font-semibold">{agentDisplayName}</h1>
                <p className="text-sm text-muted-foreground">Chat with this agent</p>
              </div>
            </div>
            {/* Model/Provider selectors */}
            <div className="flex items-center gap-2">
              <Select value={provider} onValueChange={setProvider}>
                <SelectTrigger className="h-8 w-[120px] text-xs">
                  <SelectValue placeholder="Provider" />
                </SelectTrigger>
                <SelectContent>
                  {providers
                    .filter((p) => p.configured)
                    .map((p) => (
                      <SelectItem key={p.name} value={p.name}>
                        {p.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
              <Select
                value={model || 'default'}
                onValueChange={(v) => setModel(v === 'default' ? null : v)}
              >
                <SelectTrigger className="h-8 w-[180px] text-xs">
                  <SelectValue placeholder="Model" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">Default</SelectItem>
                  {availableModels.map((m) => (
                    <SelectItem key={m.name} value={m.name}>
                      {m.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-hidden">
          <div className="mx-auto flex h-full max-w-3xl flex-col p-6">
            <ScrollArea className="flex-1 pr-4">
              <div className="space-y-4 pb-4">
                {messages.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
                    <div
                      className={cn(
                        'flex h-16 w-16 items-center justify-center rounded-xl text-white font-bold text-xl mb-4',
                        avatarColor
                      )}
                    >
                      {initials}
                    </div>
                    <p className="text-lg font-medium text-foreground mb-1">
                      Start a conversation with {agentDisplayName}
                    </p>
                    <p>Ask anything this agent can help you with.</p>
                  </div>
                )}

                {messages.map((msg, index) => (
                  <div
                    key={index}
                    className={cn(
                      'flex gap-3',
                      msg.role === 'user' ? 'justify-end' : 'justify-start'
                    )}
                  >
                    {msg.role === 'assistant' && (
                      <div
                        className={cn(
                          'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white text-sm font-semibold',
                          avatarColor
                        )}
                      >
                        {initials}
                      </div>
                    )}
                    <div
                      className={cn(
                        'max-w-[80%] rounded-lg px-4 py-2',
                        msg.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted'
                      )}
                    >
                      {msg.role === 'assistant' ? (
                        <div className="prose prose-sm dark:prose-invert prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-code:text-xs max-w-none">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      )}
                    </div>
                  </div>
                ))}

                {isLoading && (
                  <div className="flex gap-3">
                    <div
                      className={cn(
                        'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white text-sm font-semibold',
                        avatarColor
                      )}
                    >
                      {initials}
                    </div>
                    <div className="flex items-center gap-2 rounded-lg bg-muted px-4 py-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Thinking...</span>
                    </div>
                  </div>
                )}

                {error && (
                  <div className="rounded-lg bg-destructive/10 px-4 py-2 text-destructive">
                    {error}
                  </div>
                )}
              </div>
            </ScrollArea>

            <form onSubmit={handleSubmit} className="mt-4 flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={`Ask ${agentDisplayName}...`}
                disabled={isLoading || !workflowId}
                className="flex-1"
              />
              <Button type="submit" disabled={isLoading || !workflowId || !input.trim()}>
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  // Multi-agent mode: Split view with workflow graph
  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Left Panel - Chat */}
      <div className="flex w-1/2 flex-col border-r p-4">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Multi-Agent Chat</h2>
          <Select value={agentPreset} onValueChange={setAgentPreset}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select preset" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Agents</SelectItem>
              <SelectItem value="math_weather">Math + Weather</SelectItem>
              <SelectItem value="research_finance">Research + Finance</SelectItem>
              <SelectItem value="math_only">Math Only</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          {selectedAgents.map((agent) => (
            <Badge key={agent} variant="secondary">
              {agent.replace('_', ' ')}
            </Badge>
          ))}
        </div>

        <ScrollArea className="flex-1 pr-4">
          <div className="space-y-4 pb-4">
            {messages.length === 0 && (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                <p>Ask a question that requires multiple agents.</p>
              </div>
            )}

            {messages.map((msg, index) => (
              <div
                key={index}
                className={cn(
                  'flex',
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                )}
              >
                <div
                  className={cn(
                    'max-w-[80%] rounded-lg px-4 py-2',
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted'
                  )}
                >
                  {msg.role === 'assistant' ? (
                    <div className="prose prose-sm dark:prose-invert prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-code:text-xs max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-lg bg-muted px-4 py-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Agents working...</span>
                </div>
              </div>
            )}

            {error && (
              <div className="rounded-lg bg-destructive/10 px-4 py-2 text-destructive">
                {error}
              </div>
            )}
          </div>
        </ScrollArea>

        <form onSubmit={handleSubmit} className="mt-4 flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question..."
            disabled={isLoading || !workflowId}
          />
          <Button type="submit" disabled={isLoading || !workflowId || !input.trim()}>
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </form>

        {response?.agents && response.agents.length > 0 && (
          <div className="mt-4">
            <p className="text-sm text-muted-foreground">
              Agents used: {response.agents.join(', ')}
            </p>
          </div>
        )}
      </div>

      {/* Right Panel - Workflow Graph */}
      <div className="w-1/2 bg-slate-950">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
        >
          <Background color="#334155" gap={16} />
          <Controls />
          <MiniMap
            nodeColor={(node) => {
              if (node.id === 'supervisor') return '#14b8a6';
              return '#1e293b';
            }}
            style={{ background: '#0f172a' }}
          />
        </ReactFlow>
      </div>
    </div>
  );
}
