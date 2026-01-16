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
  Plus,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Collapsible } from '@/components/ui/collapsible';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { agentsApi, skillsApi, modelsApi } from '@/api';
import type { ToolTemplate, SkillMetadata, ScheduleConfig, ProviderInfo, ModelInfo } from '@/types/api';
import { cn } from '@/lib/cn';
import { TemplateSelector } from './TemplateSelector';
import type { AgentTemplate } from './templates';

interface TestMessage {
  role: 'user' | 'assistant';
  content: string;
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
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [tools, setTools] = useState<ToolTemplate[]>([]);
  const [skills, setSkills] = useState<SkillMetadata[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [toolsOrSkillsTab, setToolsOrSkillsTab] = useState<'tools' | 'skills'>('tools');
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

  // Fetch tools, categories, skills, and providers
  useEffect(() => {
    Promise.all([
      agentsApi.listTools(),
      agentsApi.listToolCategories(),
      skillsApi.list(),
      modelsApi.listProviders(),
    ])
      .then(([toolsData, categoriesData, skillsData, providersData]) => {
        setTools(toolsData);
        setCategories(categoriesData);
        setSkills(skillsData.skills);
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

  const filteredTools = selectedCategory
    ? tools.filter((t) => t.category === selectedCategory)
    : tools;

  const resetTestAgent = () => {
    // Cleanup existing test agent when config changes
    if (testAgentId) {
      agentsApi.deleteCustomAgent(testAgentId).catch(() => {});
      setTestAgentId(null);
      setTestSessionId(null);
    }
  };

  const toggleTool = (toolId: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolId) ? prev.filter((id) => id !== toolId) : [...prev, toolId]
    );
    resetTestAgent();
  };

  const toggleSkill = (skillId: string) => {
    setSelectedSkills((prev) =>
      prev.includes(skillId) ? prev.filter((id) => id !== skillId) : [...prev, skillId]
    );
    resetTestAgent();
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
    const hasToolsOrSkills = selectedTools.length > 0 || selectedSkills.length > 0;
    return hasValidName && hasValidPrompt && hasToolsOrSkills;
  };

  const canTest = () => {
    return name.trim().length >= 1 && (selectedTools.length > 0 || selectedSkills.length > 0);
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

    try {
      // Create a temporary custom agent for testing if needed
      let agentId = testAgentId;

      if (!agentId) {
        // Create a temporary agent
        agentId = `test-agent-${Date.now()}`;
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

      // Invoke the agent directly (no supervisor) for human-in-the-loop support
      const result = await agentsApi.invokeAgentDirect(agentId, {
        message: userMessage,
        session_id: testSessionId,
      });

      // Store session ID for follow-up messages
      setTestSessionId(result.session_id);

      setTestMessages((prev) => [
        ...prev,
        { role: 'assistant', content: result.response },
      ]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Test failed';
      setTestError(errorMessage);
      setTestMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${errorMessage}` },
      ]);
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
    // Map template tool names to actual tool IDs
    const toolIds = template.tools.filter((toolName) =>
      tools.some((t) => t.id === toolName)
    );
    setSelectedTools(toolIds);
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
    setSelectedTools([]);
    setSelectedSkills([]);
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
    if (selectedTools.length === 0 && selectedSkills.length === 0) messages.push('Select at least one tool or skill');
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

                {/* Toolbox Section */}
                <Collapsible
                  title="Toolbox"
                  icon={<Wrench className="h-4 w-4 text-muted-foreground" />}
                  defaultOpen={true}
                  badge={
                    (selectedTools.length > 0 || selectedSkills.length > 0) ? (
                      <Badge variant="secondary" className="ml-2 text-xs">
                        {selectedTools.length + selectedSkills.length} selected
                      </Badge>
                    ) : null
                  }
                >
                  <div className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      Equip your agent with tools and skills.
                    </p>

                    {/* Action buttons */}
                    <div className="flex gap-2 flex-wrap">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setToolsOrSkillsTab('tools')}
                        className={cn(
                          'gap-2',
                          toolsOrSkillsTab === 'tools' && 'border-primary bg-primary/10'
                        )}
                      >
                        <Plus className="h-3 w-3" />
                        Add Tool
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setToolsOrSkillsTab('skills')}
                        className={cn(
                          'gap-2',
                          toolsOrSkillsTab === 'skills' && 'border-primary bg-primary/10'
                        )}
                      >
                        <Plus className="h-3 w-3" />
                        Add Skill
                      </Button>
                    </div>

                    {/* Selected items display */}
                    {(selectedTools.length > 0 || selectedSkills.length > 0) && (
                      <div className="flex flex-wrap gap-2">
                        {selectedTools.map((toolId) => {
                          const tool = tools.find((t) => t.id === toolId);
                          return (
                            <Badge
                              key={toolId}
                              variant="secondary"
                              className="gap-1 cursor-pointer hover:bg-destructive/20"
                              onClick={() => toggleTool(toolId)}
                            >
                              <Wrench className="h-3 w-3" />
                              {tool?.name || toolId}
                              <span className="ml-1 text-muted-foreground">x</span>
                            </Badge>
                          );
                        })}
                        {selectedSkills.map((skillId) => {
                          const skill = skills.find((s) => s.id === skillId);
                          return (
                            <Badge
                              key={skillId}
                              variant="secondary"
                              className="gap-1 cursor-pointer hover:bg-destructive/20"
                              onClick={() => toggleSkill(skillId)}
                            >
                              <Sparkles className="h-3 w-3" />
                              {skill?.name || skillId}
                              <span className="ml-1 text-muted-foreground">x</span>
                            </Badge>
                          );
                        })}
                      </div>
                    )}

                    {/* Tools/Skills Selection */}
                    <Tabs value={toolsOrSkillsTab} onValueChange={(v) => setToolsOrSkillsTab(v as 'tools' | 'skills')}>
                      <TabsList className="w-full">
                        <TabsTrigger value="tools" className="flex-1 gap-2">
                          <Wrench className="h-4 w-4" />
                          Tools ({tools.length})
                        </TabsTrigger>
                        <TabsTrigger value="skills" className="flex-1 gap-2">
                          <Sparkles className="h-4 w-4" />
                          Skills ({skills.length})
                        </TabsTrigger>
                      </TabsList>

                      <TabsContent value="tools" className="mt-4">
                        {/* Category filter */}
                        <div className="flex flex-wrap gap-2 mb-4">
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

                        <div className="grid gap-2 max-h-[300px] overflow-y-auto pr-2">
                          {filteredTools.map((tool) => {
                            const isSelected = selectedTools.includes(tool.id);
                            return (
                              <button
                                key={tool.id}
                                onClick={() => toggleTool(tool.id)}
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
                                    <span className="font-medium">{tool.name}</span>
                                    <Badge variant="outline" className="text-xs">
                                      {tool.category}
                                    </Badge>
                                  </div>
                                  <p className="text-sm text-muted-foreground">{tool.description}</p>
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </TabsContent>

                      <TabsContent value="skills" className="mt-4">
                        <p className="text-sm text-muted-foreground mb-4">
                          Skills add specialized context and capabilities using progressive disclosure.
                        </p>
                        <div className="grid gap-2 max-h-[300px] overflow-y-auto pr-2">
                          {skills.length === 0 ? (
                            <div className="text-center py-8 text-muted-foreground">
                              <Sparkles className="h-8 w-8 mx-auto mb-2 opacity-50" />
                              <p>No skills available</p>
                              <Button
                                variant="link"
                                size="sm"
                                onClick={() => navigate('/skills/new')}
                                className="mt-2"
                              >
                                Create a skill
                              </Button>
                            </div>
                          ) : (
                            skills.map((skill) => {
                              const isSelected = selectedSkills.includes(skill.id);
                              return (
                                <button
                                  key={skill.id}
                                  onClick={() => toggleSkill(skill.id)}
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
                                      <span className="font-medium">{skill.name}</span>
                                      <Badge variant="outline" className="text-xs">
                                        {skill.category}
                                      </Badge>
                                      <Badge variant="secondary" className="text-xs">
                                        v{skill.version}
                                      </Badge>
                                    </div>
                                    <p className="text-sm text-muted-foreground">{skill.description}</p>
                                  </div>
                                </button>
                              );
                            })
                          )}
                        </div>
                      </TabsContent>
                    </Tabs>
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

                {/* Tools Preview */}
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-2">
                    Tools ({selectedTools.length})
                  </p>
                  {selectedTools.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {selectedTools.map((toolId) => {
                        const tool = tools.find((t) => t.id === toolId);
                        return (
                          <Badge key={toolId} variant="secondary" className="text-xs">
                            {tool?.name || toolId}
                          </Badge>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No tools selected yet...</p>
                  )}
                </div>

                {/* Skills Preview */}
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-2">
                    Skills ({selectedSkills.length})
                  </p>
                  {selectedSkills.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {selectedSkills.map((skillId) => {
                        const skill = skills.find((s) => s.id === skillId);
                        return (
                          <Badge key={skillId} variant="secondary" className="text-xs gap-1">
                            <Sparkles className="h-3 w-3" />
                            {skill?.name || skillId}
                          </Badge>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No skills selected yet...</p>
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

                    {/* Agent Node with Tools */}
                    <div className="flex items-center gap-3">
                      {/* Tools on the left */}
                      {(selectedTools.length > 0 || selectedSkills.length > 0) && (
                        <div className="flex flex-col gap-1 items-end">
                          {selectedTools.slice(0, 3).map((toolId) => {
                            const tool = tools.find((t) => t.id === toolId);
                            return (
                              <div
                                key={toolId}
                                className="flex items-center gap-1"
                              >
                                <div className="px-2 py-1 bg-blue-500/20 border border-blue-500/50 rounded text-xs text-blue-400 flex items-center gap-1">
                                  <Wrench className="h-3 w-3" />
                                  {tool?.name?.split(' ')[0] || toolId}
                                </div>
                                <div className="w-3 h-px bg-blue-500/50" />
                              </div>
                            );
                          })}
                          {selectedSkills.slice(0, 2).map((skillId) => {
                            const skill = skills.find((s) => s.id === skillId);
                            return (
                              <div
                                key={skillId}
                                className="flex items-center gap-1"
                              >
                                <div className="px-2 py-1 bg-purple-500/20 border border-purple-500/50 rounded text-xs text-purple-400 flex items-center gap-1">
                                  <Sparkles className="h-3 w-3" />
                                  {skill?.name?.split(' ')[0] || skillId}
                                </div>
                                <div className="w-3 h-px bg-purple-500/50" />
                              </div>
                            );
                          })}
                          {(selectedTools.length > 3 || selectedSkills.length > 2) && (
                            <div className="text-xs text-muted-foreground">
                              +{Math.max(0, selectedTools.length - 3) + Math.max(0, selectedSkills.length - 2)} more
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
                        {(selectedTools.length > 0 || selectedSkills.length > 0) && (
                          <div className="absolute -top-1 -right-1 w-4 h-4 bg-blue-500 rounded-full flex items-center justify-center text-[10px] text-white font-bold">
                            {selectedTools.length + selectedSkills.length}
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
                            <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                          </div>
                          {msg.role === 'user' && (
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                              <User className="h-4 w-4" />
                            </div>
                          )}
                        </div>
                      ))}
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
                          <div className="rounded-lg px-3 py-2 bg-muted">
                            <Loader2 className="h-4 w-4 animate-spin" />
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
