import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Check,
  Wrench,
  FileText,
  Send,
  Bot,
  User,
  Loader2,
  MessageSquare,
  GitBranch,
  ArrowLeft,
  Sparkles,
  Clock,
  Calendar,
  Settings,
  GripVertical,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Collapsible } from '@/components/ui/collapsible';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { agentsApi, capabilitiesApi, modelsApi } from '@/api';
import type { Capability, ScheduleConfig, ProviderInfo, ModelInfo } from '@/types/api';
import { cn } from '@/lib/cn';
import { TemplateSelector } from './TemplateSelector';
import type { AgentTemplate } from './templates';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ToolCallInfo {
  tool_name: string;
  tool_id: string;
  arguments?: string;
  result?: string;
  isLoading?: boolean;
}

interface TestMessage {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCallInfo[];
}

// Cron expression presets for easy selection
const CRON_PRESETS = [
  { label: 'Every minute', value: '* * * * *', description: 'For testing only' },
  { label: 'Every hour', value: '0 * * * *', description: 'At the start of every hour' },
  { label: 'Every day at 9am', value: '0 9 * * *', description: 'Daily at 9:00 AM' },
  { label: 'Every day at 6pm', value: '0 18 * * *', description: 'Daily at 6:00 PM' },
  { label: 'Every Monday at 9am', value: '0 9 * * 1', description: 'Weekly on Monday' },
  { label: 'Every weekday at 9am', value: '0 9 * * 1-5', description: 'Mon-Fri at 9:00 AM' },
  { label: 'First of month at 9am', value: '0 9 1 * *', description: 'Monthly on the 1st' },
];

// Helper component to render a tool call badge
function ToolCallBadge({ toolCall }: { toolCall: ToolCallInfo }) {
  const isSkillLoader = toolCall.tool_name.startsWith('load_') && toolCall.tool_name.endsWith('_skill');
  const displayName = isSkillLoader
    ? toolCall.tool_name.replace('load_', '').replace('_skill', '') + ' skill'
    : toolCall.tool_name;

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
      <span>{displayName}</span>
      {toolCall.isLoading && <span className="text-muted-foreground">loading...</span>}
    </div>
  );
}

// Generate avatar color from name
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

function getInitials(name: string): string {
  return name
    .split(/[_\s-]+/)
    .map((word) => word[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function BuilderPage() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const isEditing = !!agentId;

  // Builder state
  const [name, setName] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [selectedCapabilities, setSelectedCapabilities] = useState<string[]>([]);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Schedule state
  const [scheduleEnabled, setScheduleEnabled] = useState(false);
  const [cronExpression, setCronExpression] = useState('0 9 * * *');
  const [triggerPrompt, setTriggerPrompt] = useState('');
  const [selectedPreset, setSelectedPreset] = useState<string | null>('0 9 * * *');

  // Model settings state
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('openai');
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [temperature, setTemperature] = useState(0.7);

  // Template selection state
  const [showTemplates, setShowTemplates] = useState(!isEditing);

  // Test chat state (using direct agent invocation for human-in-the-loop)
  const [testMessages, setTestMessages] = useState<TestMessage[]>([]);
  const [testInput, setTestInput] = useState('');
  const [isTesting, setIsTesting] = useState(false);
  const [testAgentId, setTestAgentId] = useState<string | null>(null);
  const [testSessionId, setTestSessionId] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState('');
  const [streamingToolCalls, setStreamingToolCalls] = useState<ToolCallInfo[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Resizable panel state
  const [rightPanelWidth, setRightPanelWidth] = useState(400);
  const [isResizing, setIsResizing] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Handle resize drag
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !containerRef.current) return;

      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = containerRect.right - e.clientX;

      // Clamp between 300px and 800px (or 60% of container width)
      const maxWidth = Math.min(800, containerRect.width * 0.6);
      const clampedWidth = Math.max(300, Math.min(maxWidth, newWidth));

      setRightPanelWidth(clampedWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  // Fetch capabilities and providers
  useEffect(() => {
    Promise.all([
      capabilitiesApi.list(),
      capabilitiesApi.listCategories(),
      modelsApi.listProviders(),
    ])
      .then(([capabilitiesData, categoriesData, providersData]) => {
        setCapabilities(capabilitiesData.capabilities);
        setCategories(categoriesData);
        setProviders(providersData);
      })
      .catch(console.error);
  }, []);

  // Fetch available models when provider changes
  useEffect(() => {
    if (selectedProvider) {
      modelsApi
        .getProviderDetails(selectedProvider)
        .then((details) => {
          setAvailableModels(details.available_models);
        })
        .catch(console.error);
    }
  }, [selectedProvider]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [testMessages]);

  // Cleanup test agent on unmount
  useEffect(() => {
    return () => {
      if (testAgentId) {
        agentsApi.deleteCustomAgent(testAgentId).catch(() => {});
      }
    };
  }, [testAgentId]);

  const filteredCapabilities = selectedCategory
    ? capabilities.filter((c) => c.category === selectedCategory)
    : capabilities;

  const resetTestAgent = () => {
    // Cleanup existing test agent when config changes
    if (testAgentId) {
      agentsApi.deleteCustomAgent(testAgentId).catch(() => {});
      setTestAgentId(null);
      setTestSessionId(null);
    }
  };

  const toggleCapability = (capabilityId: string) => {
    setSelectedCapabilities((prev) =>
      prev.includes(capabilityId) ? prev.filter((id) => id !== capabilityId) : [...prev, capabilityId]
    );
    resetTestAgent();
  };

  // Helper functions to separate tools and skills from selected capabilities
  const getSelectedTools = () => {
    return selectedCapabilities
      .filter((id) => {
        const cap = capabilities.find((c) => c.id === id);
        return cap && cap.type === 'tool';
      })
      .flatMap((id) => {
        const cap = capabilities.find((c) => c.id === id);
        return cap ? cap.tools_provided : [];
      });
  };

  const getSelectedSkills = () => {
    return selectedCapabilities.filter((id) => {
      const cap = capabilities.find((c) => c.id === id);
      return cap && cap.type === 'skill_bundle';
    });
  };

  const handleProviderChange = (provider: string) => {
    setSelectedProvider(provider);
    setSelectedModel(null); // Reset model when provider changes
    resetTestAgent();
  };

  const handleModelChange = (model: string) => {
    setSelectedModel(model === 'default' ? null : model);
    resetTestAgent();
  };

  const handleTemperatureChange = (value: number[]) => {
    setTemperature(value[0]);
    resetTestAgent();
  };

  const canCreate = () => {
    const hasValidName = name.trim().length >= 1 && name.trim().length <= 50;
    const hasValidPrompt = systemPrompt.trim().length >= 10;
    const hasCapabilities = selectedCapabilities.length > 0;
    return hasValidName && hasValidPrompt && hasCapabilities;
  };

  const canTest = () => {
    return name.trim().length >= 1 && selectedCapabilities.length > 0;
  };

  const handleCreate = async () => {
    setIsCreating(true);
    setError(null);

    try {
      // Build schedule config if enabled
      const schedule: ScheduleConfig | null = scheduleEnabled && triggerPrompt.trim()
        ? {
            enabled: true,
            cron_expression: cronExpression,
            trigger_prompt: triggerPrompt.trim(),
            timezone: 'UTC',
          }
        : null;

      // Convert capabilities to tools and skills for the backend API
      const selectedTools = getSelectedTools();
      const selectedSkills = getSelectedSkills();

      await agentsApi.createCustomAgent({
        name: name.trim(),
        system_prompt: systemPrompt.trim(),
        tools: selectedTools.map((id) => ({ tool_id: id, config: {} })),
        skills: selectedSkills,
        schedule,
        provider: selectedProvider,
        model: selectedModel,
        temperature,
      });
      // Cleanup test agent
      if (testAgentId) {
        await agentsApi.deleteCustomAgent(testAgentId).catch(() => {});
      }
      navigate('/agents');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create agent');
    } finally {
      setIsCreating(false);
    }
  };

  const handleTestMessage = async () => {
    if (!testInput.trim() || !canTest()) return;

    const userMessage = testInput.trim();
    setTestInput('');
    setTestMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setIsTesting(true);
    setTestError(null);
    setStreamingContent('');
    setStreamingToolCalls([]);

    try {
      // Create a temporary custom agent for testing if needed
      let agentId = testAgentId;

      if (!agentId) {
        // Create a temporary agent
        agentId = `test-agent-${Date.now()}`;

        // Convert capabilities to tools and skills for the backend API
        const selectedTools = getSelectedTools();
        const selectedSkills = getSelectedSkills();

        await agentsApi.createCustomAgent({
          agent_id: agentId,
          name: name.trim() || 'Test Agent',
          system_prompt: systemPrompt.trim() || 'You are a helpful assistant.',
          tools: selectedTools.map((id) => ({ tool_id: id, config: {} })),
          skills: selectedSkills,
          provider: selectedProvider,
          model: selectedModel,
          temperature,
        });
        setTestAgentId(agentId);
      }

      // Stream the agent response
      const toolCalls: ToolCallInfo[] = [];
      let fullContent = '';

      for await (const event of agentsApi.invokeAgentDirectStream(agentId, {
        message: userMessage,
        session_id: testSessionId,
      })) {
        if (event.event === 'start' && event.session_id) {
          setTestSessionId(event.session_id);
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
        } else if (event.event === 'error') {
          throw new Error(event.error || 'Streaming error');
        }
      }

      // Add the final message with tool calls
      setTestMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: fullContent,
          toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
        },
      ]);
      setStreamingContent('');
      setStreamingToolCalls([]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Test failed';
      setTestError(errorMessage);
      setTestMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${errorMessage}` },
      ]);
      setStreamingContent('');
      setStreamingToolCalls([]);
    } finally {
      setIsTesting(false);
    }
  };

  const handleClearTest = async () => {
    setTestMessages([]);
    setTestError(null);
    if (testAgentId) {
      // Clear the session and delete the test agent
      await agentsApi.clearAgentSession(testAgentId, testSessionId || undefined).catch(() => {});
      await agentsApi.deleteCustomAgent(testAgentId).catch(() => {});
      setTestAgentId(null);
      setTestSessionId(null);
    }
  };

  const handleSelectTemplate = (template: AgentTemplate) => {
    setName(template.name);
    setSystemPrompt(template.systemPrompt);
    // Map template tools to capability IDs
    // Template tools are tool_ids, we need to find which capabilities provide them
    const capabilityIds = capabilities
      .filter((cap) =>
        template.tools.some((toolId) => cap.tools_provided.includes(toolId) || cap.id === toolId)
      )
      .map((cap) => cap.id);
    setSelectedCapabilities(capabilityIds);
    // Apply template's model settings if specified
    if (template.provider) {
      setSelectedProvider(template.provider);
    }
    if (template.model) {
      setSelectedModel(template.model);
    }
    if (template.temperature !== undefined) {
      setTemperature(template.temperature);
    }
    setShowTemplates(false);
  };

  const handleStartFromScratch = () => {
    setShowTemplates(false);
  };

  const handleBackToTemplates = () => {
    setShowTemplates(true);
    // Reset form
    setName('');
    setSystemPrompt('');
    setSelectedCapabilities([]);
    // Reset model settings
    setSelectedProvider('openai');
    setSelectedModel(null);
    setTemperature(0.7);
  };

  const avatarColor = name ? getAvatarColor(name) : 'bg-primary';
  const initials = name ? getInitials(name) : 'AG';

  // Validation messages for the create button tooltip
  const getValidationMessages = () => {
    const messages = [];
    if (name.trim().length < 1) messages.push('Add agent name');
    if (systemPrompt.trim().length < 10) messages.push('Add instructions (min 10 chars)');
    if (selectedCapabilities.length === 0) messages.push('Select at least one capability');
    return messages;
  };

  return (
    <div ref={containerRef} className="flex h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* Left Panel - Builder */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {showTemplates ? (
          /* Template Selection View */
          <div className="flex-1 overflow-auto">
            <div className="container max-w-5xl py-8">
              <TemplateSelector
                onSelectTemplate={handleSelectTemplate}
                onStartFromScratch={handleStartFromScratch}
              />
            </div>
          </div>
        ) : (
          <>
            {/* Header Bar */}
            <div className="flex items-center justify-between px-6 py-4 border-b bg-card">
              <div className="flex items-center gap-4">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleBackToTemplates}
                  className="gap-1"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back
                </Button>

                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      'flex h-10 w-10 items-center justify-center rounded-lg text-white font-semibold',
                      avatarColor
                    )}
                  >
                    {initials}
                  </div>
                  <div className="flex flex-col">
                    <Input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Agent Name"
                      maxLength={50}
                      className="h-8 text-lg font-semibold border-none shadow-none px-0 focus-visible:ring-0 bg-transparent"
                    />
                    <span className="text-xs text-muted-foreground">
                      {name.length}/50 characters
                    </span>
                  </div>
                </div>

                <Badge variant="outline" className="ml-2">
                  {isEditing ? 'Editing' : 'Draft'}
                </Badge>
              </div>

              <div className="flex items-center gap-3">
                {error && (
                  <span className="text-sm text-destructive">{error}</span>
                )}
                <Button
                  onClick={handleCreate}
                  disabled={!canCreate() || isCreating}
                  title={canCreate() ? 'Create agent' : getValidationMessages().join(', ')}
                >
                  {isCreating ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    isEditing ? 'Save Changes' : 'Create Agent'
                  )}
                </Button>
              </div>
            </div>

            {/* Main Content - Scrollable Sections */}
            <ScrollArea className="flex-1">
              <div className="p-6 space-y-4 max-w-3xl">
                {/* Instructions Section */}
                <Collapsible
                  title="Instructions"
                  icon={<FileText className="h-4 w-4 text-muted-foreground" />}
                  defaultOpen={true}
                  badge={
                    systemPrompt.length >= 10 ? (
                      <Badge variant="secondary" className="ml-2 text-xs">
                        <Check className="h-3 w-3 mr-1" />
                        Set
                      </Badge>
                    ) : null
                  }
                >
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">
                      Define how your agent should behave and respond.
                    </p>
                    <Textarea
                      value={systemPrompt}
                      onChange={(e) => setSystemPrompt(e.target.value)}
                      placeholder="You are a helpful assistant that..."
                      className="min-h-[150px] resize-y"
                    />
                    <p className="text-xs text-muted-foreground">
                      Minimum 10 characters. {systemPrompt.length} characters entered.
                    </p>
                  </div>
                </Collapsible>

                {/* Model Settings Section */}
                <Collapsible
                  title="Model Settings"
                  icon={<Settings className="h-4 w-4 text-muted-foreground" />}
                  defaultOpen={false}
                  badge={
                    <Badge variant="secondary" className="ml-2 text-xs">
                      {selectedProvider}{selectedModel ? ` / ${selectedModel}` : ''}
                    </Badge>
                  }
                >
                  <div className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      Configure which LLM provider and model your agent will use.
                    </p>

                    {/* Provider Selection */}
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Provider</label>
                      <Select value={selectedProvider} onValueChange={handleProviderChange}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select provider" />
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
                    </div>

                    {/* Model Selection */}
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Model</label>
                      <Select
                        value={selectedModel || 'default'}
                        onValueChange={handleModelChange}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select model" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="default">
                            Default ({providers.find((p) => p.name === selectedProvider)?.default_model || 'auto'})
                          </SelectItem>
                          {availableModels.map((m) => (
                            <SelectItem key={m.name} value={m.name}>
                              {m.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {/* Temperature Slider */}
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <label className="text-sm font-medium">Temperature</label>
                        <span className="text-sm text-muted-foreground">{temperature.toFixed(1)}</span>
                      </div>
                      <Slider
                        value={[temperature]}
                        onValueChange={handleTemperatureChange}
                        min={0}
                        max={2}
                        step={0.1}
                        className="w-full"
                      />
                      <p className="text-xs text-muted-foreground">
                        Lower values make responses more focused, higher values more creative.
                      </p>
                    </div>
                  </div>
                </Collapsible>

                {/* Capabilities Section */}
                <Collapsible
                  title="Capabilities"
                  icon={<Wrench className="h-4 w-4 text-muted-foreground" />}
                  defaultOpen={true}
                  badge={
                    selectedCapabilities.length > 0 ? (
                      <Badge variant="secondary" className="ml-2 text-xs">
                        {selectedCapabilities.length} selected
                      </Badge>
                    ) : null
                  }
                >
                  <div className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      Equip your agent with capabilities (tools and skills).
                    </p>

                    {/* Selected items display */}
                    {selectedCapabilities.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {selectedCapabilities.map((capId) => {
                          const cap = capabilities.find((c) => c.id === capId);
                          return (
                            <Badge
                              key={capId}
                              variant="secondary"
                              className="gap-1 cursor-pointer hover:bg-destructive/20"
                              onClick={() => toggleCapability(capId)}
                            >
                              {cap?.type === 'skill_bundle' ? (
                                <Sparkles className="h-3 w-3" />
                              ) : (
                                <Wrench className="h-3 w-3" />
                              )}
                              {cap?.name || capId}
                              <span className="ml-1 text-muted-foreground">x</span>
                            </Badge>
                          );
                        })}
                      </div>
                    )}

                    {/* Category filter */}
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant={selectedCategory === null ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setSelectedCategory(null)}
                      >
                        All
                      </Button>
                      {categories.map((cat) => (
                        <Button
                          key={cat}
                          variant={selectedCategory === cat ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => setSelectedCategory(cat)}
                        >
                          {cat}
                        </Button>
                      ))}
                    </div>

                    {/* Capabilities list */}
                    <div className="grid gap-2 max-h-[300px] overflow-y-auto pr-2">
                      {filteredCapabilities.length === 0 ? (
                        <div className="text-center py-8 text-muted-foreground">
                          <Wrench className="h-8 w-8 mx-auto mb-2 opacity-50" />
                          <p>No capabilities available</p>
                        </div>
                      ) : (
                        filteredCapabilities.map((cap) => {
                          const isSelected = selectedCapabilities.includes(cap.id);
                          return (
                            <button
                              key={cap.id}
                              onClick={() => toggleCapability(cap.id)}
                              className={cn(
                                'flex items-start gap-3 rounded-lg border p-3 text-left transition-colors',
                                isSelected
                                  ? 'border-primary bg-primary/10'
                                  : 'border-border hover:bg-muted'
                              )}
                            >
                              <div
                                className={cn(
                                  'mt-0.5 h-4 w-4 rounded border flex items-center justify-center',
                                  isSelected
                                    ? 'border-primary bg-primary'
                                    : 'border-muted-foreground'
                                )}
                              >
                                {isSelected && <Check className="h-3 w-3 text-primary-foreground" />}
                              </div>
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  {cap.type === 'skill_bundle' ? (
                                    <Sparkles className="h-4 w-4 text-purple-400" />
                                  ) : (
                                    <Wrench className="h-4 w-4 text-blue-400" />
                                  )}
                                  <span className="font-medium">{cap.name}</span>
                                  <Badge variant="outline" className="text-xs">
                                    {cap.category}
                                  </Badge>
                                  <Badge
                                    variant="secondary"
                                    className={cn(
                                      'text-xs',
                                      cap.type === 'skill_bundle' ? 'bg-purple-500/20 text-purple-400' : 'bg-blue-500/20 text-blue-400'
                                    )}
                                  >
                                    {cap.type === 'skill_bundle' ? 'Skill' : 'Tool'}
                                  </Badge>
                                </div>
                                <p className="text-sm text-muted-foreground">{cap.description}</p>
                                {cap.tools_provided.length > 0 && (
                                  <p className="text-xs text-muted-foreground mt-1">
                                    Provides: {cap.tools_provided.join(', ')}
                                  </p>
                                )}
                              </div>
                            </button>
                          );
                        })
                      )}
                    </div>
                  </div>
                </Collapsible>

                {/* Schedule Section */}
                <Collapsible
                  title="Schedule"
                  icon={<Clock className="h-4 w-4 text-muted-foreground" />}
                  defaultOpen={false}
                  badge={
                    scheduleEnabled ? (
                      <Badge variant="secondary" className="ml-2 text-xs bg-green-500/20 text-green-400">
                        <Calendar className="h-3 w-3 mr-1" />
                        Active
                      </Badge>
                    ) : null
                  }
                >
                  <div className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      Automatically run your agent on a schedule with a predefined prompt.
                    </p>

                    {/* Enable/Disable Toggle */}
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => setScheduleEnabled(!scheduleEnabled)}
                        className={cn(
                          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                          scheduleEnabled ? 'bg-primary' : 'bg-muted'
                        )}
                      >
                        <span
                          className={cn(
                            'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                            scheduleEnabled ? 'translate-x-6' : 'translate-x-1'
                          )}
                        />
                      </button>
                      <span className="text-sm font-medium">
                        {scheduleEnabled ? 'Schedule enabled' : 'Schedule disabled'}
                      </span>
                    </div>

                    {scheduleEnabled && (
                      <>
                        {/* Cron Presets */}
                        <div>
                          <label className="text-sm font-medium mb-2 block">
                            When to run
                          </label>
                          <div className="grid grid-cols-2 gap-2">
                            {CRON_PRESETS.map((preset) => (
                              <button
                                key={preset.value}
                                type="button"
                                onClick={() => {
                                  setCronExpression(preset.value);
                                  setSelectedPreset(preset.value);
                                }}
                                className={cn(
                                  'flex flex-col items-start rounded-lg border p-3 text-left transition-colors',
                                  selectedPreset === preset.value
                                    ? 'border-primary bg-primary/10'
                                    : 'border-border hover:bg-muted'
                                )}
                              >
                                <span className="text-sm font-medium">{preset.label}</span>
                                <span className="text-xs text-muted-foreground">
                                  {preset.description}
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Custom Cron Expression */}
                        <div>
                          <label className="text-sm font-medium mb-2 block">
                            Cron expression
                          </label>
                          <Input
                            value={cronExpression}
                            onChange={(e) => {
                              setCronExpression(e.target.value);
                              setSelectedPreset(null);
                            }}
                            placeholder="0 9 * * *"
                            className="font-mono"
                          />
                          <p className="text-xs text-muted-foreground mt-1">
                            Format: minute hour day month weekday (e.g., "0 9 * * *" = daily at 9am)
                          </p>
                        </div>

                        {/* Trigger Prompt */}
                        <div>
                          <label className="text-sm font-medium mb-2 block">
                            Trigger prompt
                          </label>
                          <Textarea
                            value={triggerPrompt}
                            onChange={(e) => setTriggerPrompt(e.target.value)}
                            placeholder="Run your daily report..."
                            className="min-h-[80px]"
                          />
                          <p className="text-xs text-muted-foreground mt-1">
                            This message will be sent to the agent when the schedule triggers.
                          </p>
                        </div>

                        {/* Schedule Preview */}
                        {triggerPrompt.trim() && (
                          <div className="rounded-lg border border-dashed p-3 bg-muted/50">
                            <p className="text-xs font-medium text-muted-foreground mb-1">
                              Schedule Preview
                            </p>
                            <p className="text-sm">
                              <span className="font-medium">{name || 'Agent'}</span> will run{' '}
                              <span className="text-primary font-mono">{cronExpression}</span> with
                              prompt: "{triggerPrompt.slice(0, 50)}
                              {triggerPrompt.length > 50 ? '...' : ''}"
                            </p>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </Collapsible>

                {/* Validation Summary */}
                {!canCreate() && (
                  <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                    <p className="font-medium mb-2">To create your agent, complete the following:</p>
                    <ul className="list-disc list-inside space-y-1">
                      {getValidationMessages().map((msg, i) => (
                        <li key={i}>{msg}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </ScrollArea>
          </>
        )}
      </div>

      {/* Resize Handle */}
      <div
        onMouseDown={handleMouseDown}
        className={cn(
          'w-1 hover:w-1.5 bg-border hover:bg-primary/50 cursor-col-resize transition-all flex items-center justify-center group',
          isResizing && 'w-1.5 bg-primary/50'
        )}
      >
        <div className={cn(
          'opacity-0 group-hover:opacity-100 transition-opacity',
          isResizing && 'opacity-100'
        )}>
          <GripVertical className="h-6 w-6 text-muted-foreground" />
        </div>
      </div>

      {/* Right Panel - Preview & Test */}
      <div
        className="flex flex-col bg-muted/30"
        style={{ width: rightPanelWidth }}
      >
        <Tabs defaultValue="test" className="flex flex-col h-full">
          <div className="border-b px-4 py-2">
            <TabsList className="w-full">
              <TabsTrigger value="visualize" className="flex-1 gap-2">
                <GitBranch className="h-4 w-4" />
                Visualize
              </TabsTrigger>
              <TabsTrigger value="test" className="flex-1 gap-2">
                <MessageSquare className="h-4 w-4" />
                Test Chat
              </TabsTrigger>
            </TabsList>
          </div>

          {/* Visualize Tab */}
          <TabsContent value="visualize" className="flex-1 p-4 mt-0">
            <Card className="h-full">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Agent Preview</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Agent Avatar & Name */}
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      'flex h-12 w-12 items-center justify-center rounded-lg text-white font-semibold',
                      avatarColor
                    )}
                  >
                    {initials}
                  </div>
                  <div>
                    <p className="font-medium">{name || 'Agent Name'}</p>
                    <p className="text-xs text-muted-foreground">Custom Agent</p>
                  </div>
                </div>

                {/* System Prompt Preview */}
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Instructions</p>
                  <p className="text-sm line-clamp-4">
                    {systemPrompt || 'No instructions defined yet...'}
                  </p>
                </div>

                {/* Capabilities Preview */}
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-2">
                    Capabilities ({selectedCapabilities.length})
                  </p>
                  {selectedCapabilities.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {selectedCapabilities.map((capId) => {
                        const cap = capabilities.find((c) => c.id === capId);
                        return (
                          <Badge key={capId} variant="secondary" className="text-xs gap-1">
                            {cap?.type === 'skill_bundle' ? (
                              <Sparkles className="h-3 w-3" />
                            ) : (
                              <Wrench className="h-3 w-3" />
                            )}
                            {cap?.name || capId}
                          </Badge>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No capabilities selected yet...</p>
                  )}
                </div>

                {/* Flow Diagram */}
                <div className="pt-4 border-t">
                  <p className="text-xs font-medium text-muted-foreground mb-3">Agent Flow</p>
                  <div className="flex flex-col items-center gap-2">
                    {/* User Input Node */}
                    <div className="px-4 py-2 bg-muted rounded-lg text-sm font-medium">
                      User Input
                    </div>
                    <div className="h-6 w-px bg-border" />

                    {/* Agent Node with Capabilities */}
                    <div className="flex items-center gap-3">
                      {/* Capabilities on the left */}
                      {selectedCapabilities.length > 0 && (
                        <div className="flex flex-col gap-1 items-end">
                          {selectedCapabilities.slice(0, 5).map((capId) => {
                            const cap = capabilities.find((c) => c.id === capId);
                            const isSkill = cap?.type === 'skill_bundle';
                            return (
                              <div
                                key={capId}
                                className="flex items-center gap-1"
                              >
                                <div className={cn(
                                  'px-2 py-1 border rounded text-xs flex items-center gap-1',
                                  isSkill
                                    ? 'bg-purple-500/20 border-purple-500/50 text-purple-400'
                                    : 'bg-blue-500/20 border-blue-500/50 text-blue-400'
                                )}>
                                  {isSkill ? (
                                    <Sparkles className="h-3 w-3" />
                                  ) : (
                                    <Wrench className="h-3 w-3" />
                                  )}
                                  {cap?.name?.split(' ')[0] || capId}
                                </div>
                                <div className={cn(
                                  'w-3 h-px',
                                  isSkill ? 'bg-purple-500/50' : 'bg-blue-500/50'
                                )} />
                              </div>
                            );
                          })}
                          {selectedCapabilities.length > 5 && (
                            <div className="text-xs text-muted-foreground">
                              +{selectedCapabilities.length - 5} more
                            </div>
                          )}
                        </div>
                      )}

                      {/* Agent Node */}
                      <div
                        className={cn(
                          'px-4 py-2 rounded-lg text-sm font-medium text-white relative',
                          avatarColor
                        )}
                      >
                        {name || 'Agent'}
                        {selectedCapabilities.length > 0 && (
                          <div className="absolute -top-1 -right-1 w-4 h-4 bg-blue-500 rounded-full flex items-center justify-center text-[10px] text-white font-bold">
                            {selectedCapabilities.length}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="h-6 w-px bg-border" />

                    {/* Response Node */}
                    <div className="px-4 py-2 bg-muted rounded-lg text-sm font-medium">
                      Response
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Test Chat Tab */}
          <TabsContent value="test" className="flex-1 flex flex-col p-4 mt-0 overflow-hidden">
            <Card className="flex-1 flex flex-col overflow-hidden">
              <CardHeader className="pb-3 flex-row items-center justify-between">
                <div className="flex items-center gap-2">
                  <div
                    className={cn(
                      'flex h-8 w-8 items-center justify-center rounded-lg text-white text-xs font-semibold',
                      avatarColor
                    )}
                  >
                    {initials}
                  </div>
                  <div>
                    <CardTitle className="text-sm font-medium">
                      Test {name || 'Agent'}
                    </CardTitle>
                    <p className="text-xs text-muted-foreground">
                      {canTest() ? 'Ready to test' : 'Add name and tools first'}
                    </p>
                  </div>
                </div>
                {testMessages.length > 0 && (
                  <Button variant="ghost" size="sm" onClick={handleClearTest}>
                    Clear
                  </Button>
                )}
              </CardHeader>

              {/* Messages */}
              <CardContent className="flex-1 overflow-hidden p-0">
                <ScrollArea className="h-full px-4">
                  {testMessages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full py-8 text-center">
                      <Bot className="h-12 w-12 text-muted-foreground mb-3" />
                      <p className="font-medium">Try out your agent</p>
                      <p className="text-sm text-muted-foreground mt-1 max-w-[200px]">
                        Test your agent configuration before saving
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4 py-4">
                      {testMessages.map((msg, i) => (
                        <div
                          key={i}
                          className={cn(
                            'flex gap-3',
                            msg.role === 'user' ? 'justify-end' : 'justify-start'
                          )}
                        >
                          {msg.role === 'assistant' && (
                            <div
                              className={cn(
                                'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white text-xs',
                                avatarColor
                              )}
                            >
                              {initials}
                            </div>
                          )}
                          <div
                            className={cn(
                              'rounded-lg px-3 py-2 max-w-[80%]',
                              msg.role === 'user'
                                ? 'bg-primary text-primary-foreground'
                                : 'bg-muted'
                            )}
                          >
                            {msg.role === 'assistant' ? (
                              <div className="space-y-2">
                                {/* Show tool calls if any */}
                                {msg.toolCalls && msg.toolCalls.length > 0 && (
                                  <div className="flex flex-wrap gap-1 mb-2">
                                    {msg.toolCalls.map((tc, idx) => (
                                      <ToolCallBadge key={idx} toolCall={tc} />
                                    ))}
                                  </div>
                                )}
                                <div className="text-sm prose prose-sm dark:prose-invert prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-code:text-xs max-w-none">
                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {msg.content}
                                  </ReactMarkdown>
                                </div>
                              </div>
                            ) : (
                              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                            )}
                          </div>
                          {msg.role === 'user' && (
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                              <User className="h-4 w-4" />
                            </div>
                          )}
                        </div>
                      ))}
                      {/* Streaming response indicator */}
                      {isTesting && (
                        <div className="flex gap-3">
                          <div
                            className={cn(
                              'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white text-xs',
                              avatarColor
                            )}
                          >
                            {initials}
                          </div>
                          <div className="rounded-lg px-3 py-2 bg-muted max-w-[80%]">
                            {/* Show streaming tool calls */}
                            {streamingToolCalls.length > 0 && (
                              <div className="flex flex-wrap gap-1 mb-2">
                                {streamingToolCalls.map((tc, idx) => (
                                  <ToolCallBadge key={idx} toolCall={tc} />
                                ))}
                              </div>
                            )}
                            {/* Show streaming content or loading indicator */}
                            {streamingContent ? (
                              <div className="text-sm prose prose-sm dark:prose-invert prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-code:text-xs max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                  {streamingContent}
                                </ReactMarkdown>
                              </div>
                            ) : (
                              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                {streamingToolCalls.length > 0
                                  ? 'Processing...'
                                  : 'Thinking...'}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                      <div ref={messagesEndRef} />
                    </div>
                  )}
                </ScrollArea>
              </CardContent>

              {/* Input */}
              <div className="p-4 border-t">
                {testError && (
                  <p className="text-xs text-destructive mb-2">{testError}</p>
                )}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleTestMessage();
                  }}
                  className="flex gap-2"
                >
                  <Input
                    value={testInput}
                    onChange={(e) => setTestInput(e.target.value)}
                    placeholder={canTest() ? 'Test your agent...' : 'Configure agent first'}
                    disabled={!canTest() || isTesting}
                    className="flex-1"
                  />
                  <Button
                    type="submit"
                    size="icon"
                    disabled={!canTest() || !testInput.trim() || isTesting}
                  >
                    {isTesting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </form>
              </div>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
