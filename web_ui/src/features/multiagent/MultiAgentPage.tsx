import { useEffect, useMemo, useState, useRef } from 'react';
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
import { Send, Loader2, ArrowLeft, Check, Wrench, Sparkles, BookOpen, Cpu } from 'lucide-react';
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
import { agentsApi, type UnifiedAgentInfo } from '@/api';
import { useSettingsStore } from '@/stores';
import { useMCPStore } from '@/stores/mcpStore';
import { cn } from '@/lib/cn';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChatSettingsBar, ChatSettingsPanel, ImageUpload, ImagePreviewGrid, ApprovalCard, StarterPrompts } from '@/components/chat';
import type { ApprovalRequestEvent } from '@/components/chat';
import { MCPServerToggle } from '@/features/chat/MCPServerToggle';
import { useImageUpload } from '@/hooks/useImageUpload';
import type { StarterPromptCategory } from '@/types/api';

// Tool call tracking for skill/tool badges
interface ToolCallInfo {
  tool_name: string;
  tool_id: string;
  arguments?: string;
  result?: string;
  isLoading?: boolean;
  agent_name?: string; // Which agent made this call
}

// Message with optional tool calls, agent info, and images
interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCallInfo[];
  agentsUsed?: string[]; // Agents that contributed to this response
  images?: string[]; // Attached images
}

// Helper component to render a tool call badge
function ToolCallBadge({ toolCall, showAgent = false }: { toolCall: ToolCallInfo; showAgent?: boolean }) {
  const isSkillLoader = toolCall.tool_name.startsWith('load_') && toolCall.tool_name.endsWith('_skill');
  const isTransfer = toolCall.tool_name.startsWith('transfer_to_');
  const displayName = isSkillLoader
    ? toolCall.tool_name.replace('load_', '').replace('_skill', '') + ' skill'
    : isTransfer
    ? toolCall.tool_name.replace('transfer_to_', '').replace(/_/g, ' ')
    : toolCall.tool_name;

  // Skip rendering transfer tools - they're internal to the supervisor
  if (isTransfer) return null;

  return (
    <div className={cn(
      'inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs',
      isSkillLoader
        ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
        : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
    )}>
      {toolCall.isLoading ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <Check className="h-3 w-3" />
      )}
      {isSkillLoader ? (
        <Sparkles className="h-3 w-3" />
      ) : (
        <Wrench className="h-3 w-3" />
      )}
      {showAgent && toolCall.agent_name && (
        <span className="text-muted-foreground">{toolCall.agent_name.replace(/_/g, ' ')}:</span>
      )}
      <span>{displayName}</span>
      {toolCall.isLoading && <span className="text-muted-foreground">loading...</span>}
    </div>
  );
}

const AGENT_PRESETS: Record<string, string[]> = {
  sql_expert: ['sql_expert'],
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
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isReady, setIsReady] = useState(false); // Track if agent/workflow is ready
  const [showSettings, setShowSettings] = useState(false);
  const [showMCPPanel, setShowMCPPanel] = useState(false);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequestEvent[]>([]);
  const [agentDetails, setAgentDetails] = useState<UnifiedAgentInfo | null>(null);
  const [starterPrompts, setStarterPrompts] = useState<StarterPromptCategory[]>([]);

  // Streaming state for tool call display
  const [streamingContent, setStreamingContent] = useState('');
  const [streamingToolCalls, setStreamingToolCalls] = useState<ToolCallInfo[]>([]);
  const [activeAgent, setActiveAgent] = useState<string | null>(null); // Currently processing agent
  const [agentsUsedInStream, setAgentsUsedInStream] = useState<string[]>([]); // Agents that have contributed
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Use the shared image upload hook
  const {
    selectedImages,
    fileInputRef,
    handleImageSelect,
    handleRemoveImage,
    handlePaste,
    clearImages,
  } = useImageUpload();

  const { provider, model, temperature, agentPreset, setAgentPreset } = useSettingsStore();
  // MCP store - getEnabledServers available for future MCP integration with agents
  useMCPStore();

  // Check if we're in single-agent mode (from ?agent= query param)
  const singleAgentName = searchParams.get('agent');
  const customAgentId = searchParams.get('id'); // Custom agent ID
  const agentType = searchParams.get('type'); // 'custom' or undefined (built-in)
  const isCustomAgent = agentType === 'custom' && !!customAgentId;
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

  // Fetch agent details for single-agent mode (to get skills, provider, model info)
  useEffect(() => {
    if (isSingleAgentMode) {
      const agentId = isCustomAgent && customAgentId ? customAgentId : singleAgentName;
      if (agentId) {
        agentsApi.getAgent(agentId)
          .then(setAgentDetails)
          .catch((err) => {
            console.error('Failed to fetch agent details:', err);
            setAgentDetails(null);
          });
      }
    } else {
      setAgentDetails(null);
    }
  }, [isSingleAgentMode, isCustomAgent, customAgentId, singleAgentName]);

  // Fetch starter prompts for single-agent mode
  useEffect(() => {
    if (isSingleAgentMode) {
      const agentId = isCustomAgent && customAgentId ? customAgentId : singleAgentName;
      if (agentId) {
        agentsApi.getStarterPrompts(agentId)
          .then((response) => setStarterPrompts(response.categories))
          .catch((err) => {
            console.error('Failed to fetch starter prompts:', err);
            setStarterPrompts([]);
          });
      }
    } else {
      setStarterPrompts([]);
    }
  }, [isSingleAgentMode, isCustomAgent, customAgentId, singleAgentName]);

  // Create workflow when agents change (only for built-in agents)
  useEffect(() => {
    let currentWorkflowId: string | null = null;
    let isCancelled = false;

    // Clear conversation state when switching workflows/presets
    setSessionId(null);
    setMessages([]);
    setError(null);
    setIsReady(false);

    // For custom agents, no workflow needed - just mark as ready
    if (isCustomAgent) {
      setIsReady(true);
      return;
    }

    // For built-in agents, create a workflow
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
            setIsReady(true);
          } else {
            // Effect was cancelled, clean up the workflow we just created
            agentsApi.deleteWorkflow(result.workflow_id).catch(console.error);
          }
        })
        .catch((err) => {
          if (!isCancelled) {
            console.error('Failed to create workflow:', err);
            setError('Failed to create workflow. Please try again.');
          }
        });
    }

    return () => {
      isCancelled = true;
      if (currentWorkflowId) {
        agentsApi.deleteWorkflow(currentWorkflowId).catch(console.error);
      }
    };
  }, [selectedAgents, provider, isCustomAgent]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // Handle starter prompt selection - populate input and auto-submit
  const handleStarterPromptSelect = (prompt: string) => {
    setInput(prompt);
    // Auto-submit after a short delay to allow UI to update
    setTimeout(() => {
      const form = document.querySelector('form');
      if (form) {
        form.requestSubmit();
      }
    }, 100);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading || !isReady) return;

    const userMessage = input.trim();
    const userImages = selectedImages.length > 0 ? [...selectedImages] : undefined;

    setMessages((prev) => [...prev, { role: 'user', content: userMessage, images: userImages }]);
    setInput('');
    clearImages(); // Clear images after adding to message
    setIsLoading(true);
    setError(null);
    setStreamingContent('');
    setStreamingToolCalls([]);
    setActiveAgent(null);
    setAgentsUsedInStream([]);

    try {
      // For single-agent mode (built-in or custom), use streaming API to show tool calls
      if (isSingleAgentMode) {
        const agentId = isCustomAgent && customAgentId ? customAgentId : singleAgentName;
        const toolCalls: ToolCallInfo[] = [];
        let fullContent = '';

        for await (const event of agentsApi.invokeAgentStream(agentId, {
          message: userMessage,
          images: userImages,
          session_id: sessionId,
          provider,
          model,
          temperature,
        })) {
          if (event.event === 'start' && event.session_id) {
            setSessionId(event.session_id);
          } else if (event.event === 'tool_call') {
            // Add new tool call (loading state)
            const newToolCall: ToolCallInfo = {
              tool_name: event.tool_name || 'unknown',
              tool_id: event.tool_id || '',
              arguments: event.arguments,
              isLoading: true,
            };
            toolCalls.push(newToolCall);
            setStreamingToolCalls([...toolCalls]);
          } else if (event.event === 'tool_result') {
            // Update the tool call with result
            const toolCall = toolCalls.find((tc) => tc.tool_id === event.tool_id);
            if (toolCall) {
              toolCall.result = event.result;
              toolCall.isLoading = false;
              setStreamingToolCalls([...toolCalls]);
            }
          } else if (event.event === 'token' && event.content) {
            fullContent += event.content;
            setStreamingContent(fullContent);
          } else if (event.event === 'approval_request') {
            // HITL approval required - update tool call to show pending approval
            const toolCall = toolCalls.find((tc) => tc.tool_id === event.tool_id);
            if (toolCall) {
              toolCall.result = 'Pending approval...';
              toolCall.isLoading = false;
              setStreamingToolCalls([...toolCalls]);
            }

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
            // Use response from done event as fallback if no tokens were streamed
            if (!fullContent && event.response) {
              fullContent = event.response;
              setStreamingContent(fullContent);
            }
          } else if (event.event === 'error') {
            throw new Error(event.error || 'Streaming error');
          }
        }

        // Add the final message with tool calls
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: fullContent,
            toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
          },
        ]);
        setStreamingContent('');
        setStreamingToolCalls([]);
      } else if (workflowId) {
        // Use streaming workflow API for multi-agent mode
        const toolCalls: ToolCallInfo[] = [];
        const usedAgents: string[] = [];
        let fullContent = '';

        for await (const event of agentsApi.invokeWorkflowStream(workflowId, {
          message: userMessage,
          images: userImages,
          session_id: sessionId,
        })) {
          if (event.event === 'start' && event.session_id) {
            setSessionId(event.session_id);
          } else if (event.event === 'agent_start' && event.agent_name) {
            // Track which agent is currently working
            setActiveAgent(event.agent_name);
            if (!usedAgents.includes(event.agent_name)) {
              usedAgents.push(event.agent_name);
              setAgentsUsedInStream([...usedAgents]);
            }
          } else if (event.event === 'agent_end') {
            setActiveAgent(null);
          } else if (event.event === 'tool_call') {
            // Add new tool call (loading state) with agent info
            const newToolCall: ToolCallInfo = {
              tool_name: event.tool_name || 'unknown',
              tool_id: event.tool_id || '',
              arguments: event.arguments,
              agent_name: event.agent_name || undefined,
              isLoading: true,
            };
            toolCalls.push(newToolCall);
            setStreamingToolCalls([...toolCalls]);
          } else if (event.event === 'tool_result') {
            // Update the tool call with result
            const toolCall = toolCalls.find((tc) => tc.tool_id === event.tool_id);
            if (toolCall) {
              toolCall.result = event.result;
              toolCall.isLoading = false;
              setStreamingToolCalls([...toolCalls]);
            }
          } else if (event.event === 'token' && event.content) {
            fullContent += event.content;
            setStreamingContent(fullContent);
          } else if (event.event === 'done') {
            // Use response from done event as fallback if no tokens were streamed
            if (!fullContent && event.response) {
              fullContent = event.response;
              setStreamingContent(fullContent);
            }
          } else if (event.event === 'error') {
            throw new Error(event.error || 'Streaming error');
          }
        }

        // Add the final message with tool calls and agents used
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: fullContent,
            toolCalls: toolCalls.filter((tc) => !tc.tool_name.startsWith('transfer_to_')).length > 0
              ? toolCalls.filter((tc) => !tc.tool_name.startsWith('transfer_to_'))
              : undefined,
            agentsUsed: usedAgents.length > 0 ? usedAgents : undefined,
          },
        ]);
        setStreamingContent('');
        setStreamingToolCalls([]);
        setActiveAgent(null);
        setAgentsUsedInStream([]);
      } else {
        throw new Error('No agent or workflow available');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Agent execution failed');
      setStreamingContent('');
      setStreamingToolCalls([]);
      setActiveAgent(null);
      setAgentsUsedInStream([]);
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
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-semibold">{agentDisplayName}</h1>
                  {agentDetails?.type === 'custom' && (
                    <Badge variant="outline" className="text-xs">
                      <Cpu className="h-3 w-3 mr-1" />
                      Custom
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  {/* Skills badges */}
                  {agentDetails?.skills && agentDetails.skills.length > 0 && (
                    <div className="flex items-center gap-1">
                      <BookOpen className="h-3 w-3 text-muted-foreground" />
                      {agentDetails.skills.map((skill) => (
                        <Badge key={skill} variant="secondary" className="text-xs bg-purple-500/20 text-purple-400 border-purple-500/30">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  )}
                  {/* Tools count if no skills */}
                  {(!agentDetails?.skills || agentDetails.skills.length === 0) && agentDetails?.tools && agentDetails.tools.length > 0 && (
                    <Badge variant="secondary" className="text-xs">
                      <Wrench className="h-3 w-3 mr-1" />
                      {agentDetails.tools.length} tools
                    </Badge>
                  )}
                  {/* Provider/Model info - shows current session settings */}
                  {provider && (
                    <Badge variant="outline" className="text-xs">
                      {provider}
                      {model && ` / ${model.split('/').pop()}`}
                    </Badge>
                  )}
                </div>
              </div>
            </div>
            {/* Settings bar (compact mode) */}
            <ChatSettingsBar
              showSettings={showSettings}
              onToggleSettings={() => setShowSettings(!showSettings)}
              compact={true}
            />
          </div>
        </div>

        {/* Settings Panel */}
        {showSettings && (
          <div className="border-b bg-card px-6 py-4">
            <ChatSettingsPanel compact={true} />
            <div className="mt-3">
              <MCPServerToggle
                isOpen={showMCPPanel}
                onToggle={() => setShowMCPPanel(!showMCPPanel)}
              />
            </div>
          </div>
        )}

        {/* Chat area */}
        <div className="flex-1 overflow-hidden">
          <div className="mx-auto flex h-full max-w-3xl flex-col p-6">
            <ScrollArea className="flex-1 pr-4">
              <div className="space-y-4 pb-4">
                {messages.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <div
                      className={cn(
                        'flex h-16 w-16 items-center justify-center rounded-xl text-white font-bold text-xl mb-4',
                        avatarColor
                      )}
                    >
                      {initials}
                    </div>
                    {starterPrompts.length > 0 ? (
                      <StarterPrompts
                        categories={starterPrompts}
                        onSelectPrompt={handleStarterPromptSelect}
                        className="w-full max-w-2xl"
                      />
                    ) : (
                      <>
                        <p className="text-lg font-medium text-foreground mb-1">
                          Start a conversation with {agentDisplayName}
                        </p>
                        <p className="text-muted-foreground">
                          Ask anything this agent can help you with.
                        </p>
                      </>
                    )}
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
                    <div className="flex flex-col gap-2 max-w-[80%]">
                      {/* Display images if present */}
                      {msg.role === 'user' && msg.images && msg.images.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {msg.images.map((img, imgIdx) => (
                            <img
                              key={imgIdx}
                              src={img}
                              alt={`Uploaded image ${imgIdx + 1}`}
                              className="max-h-32 rounded cursor-pointer hover:opacity-90 transition-opacity"
                              onClick={() => window.open(img, '_blank')}
                            />
                          ))}
                        </div>
                      )}
                      {/* Tool call badges for assistant messages */}
                      {msg.role === 'assistant' && msg.toolCalls && msg.toolCalls.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {msg.toolCalls.map((tc, tcIdx) => (
                            <ToolCallBadge key={tcIdx} toolCall={tc} />
                          ))}
                        </div>
                      )}
                      <div
                        className={cn(
                          'rounded-lg px-4 py-2',
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
                    <div className="flex flex-col gap-2 max-w-[80%]">
                      {/* Show streaming tool calls */}
                      {streamingToolCalls.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {streamingToolCalls.map((tc, idx) => (
                            <ToolCallBadge key={idx} toolCall={tc} />
                          ))}
                        </div>
                      )}
                      {/* Show streaming content or thinking indicator */}
                      <div className="rounded-lg bg-muted px-4 py-2">
                        {streamingContent ? (
                          <div className="prose prose-sm dark:prose-invert prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-code:text-xs max-w-none">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {streamingContent}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span>{streamingToolCalls.length > 0 ? 'Processing...' : 'Thinking...'}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {error && (
                  <div className="rounded-lg bg-destructive/10 px-4 py-2 text-destructive">
                    {error}
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
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>

            {/* Input area */}
            <div className="mt-4">
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
                  disabled={isLoading || !isReady}
                />

                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onPaste={handlePaste}
                  placeholder={`Ask ${agentDisplayName}... (paste images)`}
                  disabled={isLoading || !isReady}
                  className="flex-1"
                />
                <Button type="submit" disabled={isLoading || !isReady || !input.trim()}>
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
      </div>
    );
  }

  // Multi-agent mode: Split view with workflow graph
  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Left Panel - Chat */}
      <div className="flex w-1/2 flex-col border-r">
        {/* Header with settings */}
        <div className="border-b px-4 py-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Multi-Agent Chat</h2>
            <div className="flex items-center gap-2">
              <Select value={agentPreset} onValueChange={setAgentPreset}>
                <SelectTrigger className="w-[140px] h-8">
                  <SelectValue placeholder="Select preset" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sql_expert">SQL Expert</SelectItem>
                </SelectContent>
              </Select>
              <ChatSettingsBar
                showSettings={showSettings}
                onToggleSettings={() => setShowSettings(!showSettings)}
                compact={true}
              />
            </div>
          </div>
        </div>

        {/* Settings Panel */}
        {showSettings && (
          <div className="border-b px-4 py-3">
            <ChatSettingsPanel compact={true} />
            <div className="mt-3">
              <MCPServerToggle
                isOpen={showMCPPanel}
                onToggle={() => setShowMCPPanel(!showMCPPanel)}
              />
            </div>
          </div>
        )}

        <div className="flex-1 flex flex-col p-4 overflow-hidden">
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
                  <div className="flex flex-col gap-2 max-w-[80%]">
                    {/* Display images if present */}
                    {msg.role === 'user' && msg.images && msg.images.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {msg.images.map((img, imgIdx) => (
                          <img
                            key={imgIdx}
                            src={img}
                            alt={`Uploaded image ${imgIdx + 1}`}
                            className="max-h-32 rounded cursor-pointer hover:opacity-90 transition-opacity"
                            onClick={() => window.open(img, '_blank')}
                          />
                        ))}
                      </div>
                    )}
                    {/* Agents used badges for assistant messages */}
                    {msg.role === 'assistant' && msg.agentsUsed && msg.agentsUsed.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {msg.agentsUsed.map((agent, agentIdx) => (
                          <div
                            key={agentIdx}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-teal-500/20 text-teal-400 border border-teal-500/30"
                          >
                            <Check className="h-3 w-3" />
                            <span>{agent.replace(/_/g, ' ')}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {/* Tool call badges for assistant messages */}
                    {msg.role === 'assistant' && msg.toolCalls && msg.toolCalls.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {msg.toolCalls.map((tc, tcIdx) => (
                          <ToolCallBadge key={tcIdx} toolCall={tc} showAgent={true} />
                        ))}
                      </div>
                    )}
                    <div
                      className={cn(
                        'rounded-lg px-4 py-2',
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
                </div>
              ))}

              {isLoading && (
                <div className="flex flex-col gap-2 max-w-[80%]">
                  {/* Show agents used so far during streaming */}
                  {agentsUsedInStream.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {agentsUsedInStream.map((agent, idx) => (
                        <div
                          key={idx}
                          className={cn(
                            'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border',
                            activeAgent === agent
                              ? 'bg-teal-500/30 text-teal-300 border-teal-400/50'
                              : 'bg-teal-500/20 text-teal-400 border-teal-500/30'
                          )}
                        >
                          {activeAgent === agent ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Check className="h-3 w-3" />
                          )}
                          <span>{agent.replace(/_/g, ' ')}</span>
                          {activeAgent === agent && (
                            <span className="text-teal-300/70">working...</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {/* Show streaming tool calls */}
                  {streamingToolCalls.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {streamingToolCalls.map((tc, idx) => (
                        <ToolCallBadge key={idx} toolCall={tc} showAgent={true} />
                      ))}
                    </div>
                  )}
                  {/* Show streaming content or thinking indicator */}
                  <div className="rounded-lg bg-muted px-4 py-2">
                    {streamingContent ? (
                      <div className="prose prose-sm dark:prose-invert prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-code:text-xs max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {streamingContent}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>
                          {activeAgent
                            ? `${activeAgent.replace(/_/g, ' ')} working...`
                            : streamingToolCalls.length > 0
                            ? 'Processing tools...'
                            : 'Agents coordinating...'}
                        </span>
                      </div>
                    )}
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

          {/* Input area */}
          <div className="mt-4">
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
                disabled={isLoading || !isReady}
              />

              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPaste={handlePaste}
                placeholder="Ask a question... (paste images)"
                disabled={isLoading || !isReady}
              />
              <Button type="submit" disabled={isLoading || !isReady || !input.trim()}>
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
