import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Check,
  ChevronRight,
  Wrench,
  FileText,
  Eye,
  Send,
  Bot,
  User,
  Loader2,
  MessageSquare,
  GitBranch,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { agentsApi } from '@/api';
import type { ToolTemplate } from '@/types/api';
import { cn } from '@/lib/cn';

const STEPS = [
  { id: 1, name: 'Name', icon: FileText },
  { id: 2, name: 'Prompt', icon: FileText },
  { id: 3, name: 'Tools', icon: Wrench },
  { id: 4, name: 'Review', icon: Eye },
];

interface TestMessage {
  role: 'user' | 'assistant';
  content: string;
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
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [tools, setTools] = useState<ToolTemplate[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Test chat state
  const [testMessages, setTestMessages] = useState<TestMessage[]>([]);
  const [testInput, setTestInput] = useState('');
  const [isTesting, setIsTesting] = useState(false);
  const [testWorkflowId, setTestWorkflowId] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch tools and categories
  useEffect(() => {
    Promise.all([agentsApi.listTools(), agentsApi.listToolCategories()])
      .then(([toolsData, categoriesData]) => {
        setTools(toolsData);
        setCategories(categoriesData);
      })
      .catch(console.error);
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [testMessages]);

  // Cleanup test workflow on unmount
  useEffect(() => {
    return () => {
      if (testWorkflowId) {
        agentsApi.deleteWorkflow(testWorkflowId).catch(() => {});
      }
    };
  }, [testWorkflowId]);

  const filteredTools = selectedCategory
    ? tools.filter((t) => t.category === selectedCategory)
    : tools;

  const toggleTool = (toolId: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolId) ? prev.filter((id) => id !== toolId) : [...prev, toolId]
    );
    // Reset test workflow when tools change
    if (testWorkflowId) {
      agentsApi.deleteWorkflow(testWorkflowId).catch(() => {});
      setTestWorkflowId(null);
    }
  };

  const canProceed = () => {
    switch (step) {
      case 1:
        return name.trim().length >= 1 && name.trim().length <= 50;
      case 2:
        return systemPrompt.trim().length >= 10;
      case 3:
        return selectedTools.length > 0;
      case 4:
        return true;
      default:
        return false;
    }
  };

  const canTest = () => {
    return name.trim().length >= 1 && selectedTools.length > 0;
  };

  const handleCreate = async () => {
    setIsCreating(true);
    setError(null);

    try {
      await agentsApi.createCustomAgent({
        name: name.trim(),
        system_prompt: systemPrompt.trim(),
        tools: selectedTools.map((id) => ({ tool_id: id, config: {} })),
      });
      // Cleanup test workflow
      if (testWorkflowId) {
        await agentsApi.deleteWorkflow(testWorkflowId).catch(() => {});
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
      let workflowId = testWorkflowId;

      if (!workflowId) {
        // Create a temporary agent
        const tempAgentId = `test-agent-${Date.now()}`;
        await agentsApi.createCustomAgent({
          agent_id: tempAgentId,
          name: name.trim() || 'Test Agent',
          system_prompt: systemPrompt.trim() || 'You are a helpful assistant.',
          tools: selectedTools.map((id) => ({ tool_id: id, config: {} })),
        });

        // Create a workflow with the temporary agent
        workflowId = `test-workflow-${Date.now()}`;
        await agentsApi.createWorkflow({
          workflow_id: workflowId,
          agents: [tempAgentId],
        });
        setTestWorkflowId(workflowId);
      }

      // Invoke the workflow
      const result = await agentsApi.invokeWorkflow(workflowId, {
        message: userMessage,
      });

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
    if (testWorkflowId) {
      await agentsApi.deleteWorkflow(testWorkflowId).catch(() => {});
      setTestWorkflowId(null);
    }
  };

  const avatarColor = name ? getAvatarColor(name) : 'bg-primary';
  const initials = name ? getInitials(name) : 'AG';

  return (
    <div className="flex h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* Left Panel - Builder */}
      <div className="flex-1 overflow-auto border-r">
        <div className="container max-w-3xl py-8">
          <div className="mb-8">
            <h1 className="text-2xl font-bold">
              {isEditing ? 'Edit Agent' : 'Create Custom Agent'}
            </h1>
            <p className="text-muted-foreground">
              Build a custom agent with your own tools and instructions.
            </p>
          </div>

          {/* Step indicator */}
          <div className="mb-8 flex items-center justify-center">
            {STEPS.map((s, index) => {
              const Icon = s.icon;
              const isActive = step === s.id;
              const isCompleted = step > s.id;

              return (
                <div key={s.id} className="flex items-center">
                  <button
                    onClick={() => isCompleted && setStep(s.id)}
                    disabled={!isCompleted}
                    className={cn(
                      'flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors',
                      isActive && 'border-primary bg-primary text-primary-foreground',
                      isCompleted && 'border-primary bg-primary/20 text-primary',
                      !isActive && !isCompleted && 'border-muted text-muted-foreground'
                    )}
                  >
                    {isCompleted ? <Check className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
                  </button>
                  <span
                    className={cn(
                      'ml-2 text-sm font-medium',
                      isActive ? 'text-foreground' : 'text-muted-foreground'
                    )}
                  >
                    {s.name}
                  </span>
                  {index < STEPS.length - 1 && (
                    <ChevronRight className="mx-4 h-5 w-5 text-muted-foreground" />
                  )}
                </div>
              );
            })}
          </div>

          {/* Step content */}
          <Card>
            <CardContent className="pt-6">
              {step === 1 && (
                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-medium">Agent Name</label>
                    <Input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="My Custom Agent"
                      maxLength={50}
                      className="mt-2"
                    />
                    <p className="mt-1 text-sm text-muted-foreground">
                      {name.length}/50 characters
                    </p>
                  </div>
                </div>
              )}

              {step === 2 && (
                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-medium">System Prompt</label>
                    <Textarea
                      value={systemPrompt}
                      onChange={(e) => setSystemPrompt(e.target.value)}
                      placeholder="You are a helpful assistant that..."
                      className="mt-2 min-h-[200px]"
                    />
                    <p className="mt-1 text-sm text-muted-foreground">
                      Minimum 10 characters. {systemPrompt.length} characters.
                    </p>
                  </div>
                </div>
              )}

              {step === 3 && (
                <div className="space-y-4">
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

                  <ScrollArea className="h-[300px]">
                    <div className="grid gap-2">
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
                                'mt-0.5 h-4 w-4 rounded border',
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
                  </ScrollArea>

                  <p className="text-sm text-muted-foreground">
                    {selectedTools.length} tool(s) selected
                  </p>
                </div>
              )}

              {step === 4 && (
                <div className="space-y-6">
                  <div>
                    <h3 className="font-medium">Name</h3>
                    <p className="text-muted-foreground">{name}</p>
                  </div>
                  <div>
                    <h3 className="font-medium">System Prompt</h3>
                    <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                      {systemPrompt}
                    </p>
                  </div>
                  <div>
                    <h3 className="font-medium">Tools ({selectedTools.length})</h3>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selectedTools.map((toolId) => {
                        const tool = tools.find((t) => t.id === toolId);
                        return (
                          <Badge key={toolId} variant="secondary">
                            {tool?.name || toolId}
                          </Badge>
                        );
                      })}
                    </div>
                  </div>

                  {error && (
                    <div className="rounded-lg bg-destructive/10 px-4 py-2 text-destructive">
                      {error}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Navigation */}
          <div className="mt-6 flex justify-between">
            <Button
              variant="outline"
              onClick={() => setStep((s) => Math.max(1, s - 1))}
              disabled={step === 1}
            >
              Back
            </Button>

            {step < 4 ? (
              <Button onClick={() => setStep((s) => s + 1)} disabled={!canProceed()}>
                Continue
              </Button>
            ) : (
              <Button onClick={handleCreate} disabled={isCreating || !canProceed()}>
                {isCreating ? 'Creating...' : 'Create Agent'}
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Right Panel - Preview & Test */}
      <div className="w-[400px] flex flex-col bg-muted/30">
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
                  <p className="text-xs font-medium text-muted-foreground mb-1">System Prompt</p>
                  <p className="text-sm line-clamp-4">
                    {systemPrompt || 'No system prompt defined yet...'}
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

                {/* Flow Diagram */}
                <div className="pt-4 border-t">
                  <p className="text-xs font-medium text-muted-foreground mb-3">Agent Flow</p>
                  <div className="flex flex-col items-center gap-2">
                    <div className="px-4 py-2 bg-muted rounded-lg text-sm font-medium">
                      User Input
                    </div>
                    <div className="h-6 w-px bg-border" />
                    <div
                      className={cn(
                        'px-4 py-2 rounded-lg text-sm font-medium text-white',
                        avatarColor
                      )}
                    >
                      {name || 'Agent'}
                    </div>
                    <div className="h-6 w-px bg-border" />
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
