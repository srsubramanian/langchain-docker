import { useEffect, useState } from 'react';
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
import { Send, Loader2 } from 'lucide-react';
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
import { agentsApi } from '@/api';
import { useSettingsStore } from '@/stores';
import type { WorkflowInvokeResponse } from '@/types/api';
import { cn } from '@/lib/cn';

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

export function MultiAgentPage() {
  const [input, setInput] = useState('');
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState<WorkflowInvokeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);

  const { provider, agentPreset, setAgentPreset } = useSettingsStore();

  const selectedAgents = AGENT_PRESETS[agentPreset] || AGENT_PRESETS.all;
  const { nodes: initialNodes, edges: initialEdges } = generateWorkflowGraph(selectedAgents);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update graph when preset changes
  useEffect(() => {
    const { nodes: newNodes, edges: newEdges } = generateWorkflowGraph(selectedAgents);
    setNodes(newNodes);
    setEdges(newEdges);
  }, [agentPreset, selectedAgents, setNodes, setEdges]);

  // Create workflow when agents change
  useEffect(() => {
    if (selectedAgents.length > 0) {
      agentsApi
        .createWorkflow({
          agents: selectedAgents,
          provider,
        })
        .then((result) => {
          setWorkflowId(result.workflow_id);
        })
        .catch(console.error);
    }

    return () => {
      if (workflowId) {
        agentsApi.deleteWorkflow(workflowId).catch(console.error);
      }
    };
  }, [selectedAgents, provider]);

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
      });
      setResponse(result);
      setMessages((prev) => [...prev, { role: 'assistant', content: result.response }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Workflow execution failed');
    } finally {
      setIsLoading(false);
    }
  };

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
                  <p className="whitespace-pre-wrap">{msg.content}</p>
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

        {response?.agents_used && response.agents_used.length > 0 && (
          <div className="mt-4">
            <p className="text-sm text-muted-foreground">
              Agents used: {response.agents_used.join(', ')}
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
