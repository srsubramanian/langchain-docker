import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Check, ChevronRight, Wrench, FileText, Eye } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { agentsApi } from '@/api';
import type { ToolTemplate } from '@/types/api';
import { cn } from '@/lib/cn';

const STEPS = [
  { id: 1, name: 'Name', icon: FileText },
  { id: 2, name: 'Prompt', icon: FileText },
  { id: 3, name: 'Tools', icon: Wrench },
  { id: 4, name: 'Review', icon: Eye },
];

export function BuilderPage() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const isEditing = !!agentId;

  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [tools, setTools] = useState<ToolTemplate[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch tools and categories
  useEffect(() => {
    Promise.all([agentsApi.listTools(), agentsApi.listToolCategories()])
      .then(([toolsData, categoriesData]) => {
        setTools(toolsData);
        setCategories(categoriesData);
      })
      .catch(console.error);
  }, []);

  const filteredTools = selectedCategory
    ? tools.filter((t) => t.category === selectedCategory)
    : tools;

  const toggleTool = (toolId: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolId) ? prev.filter((id) => id !== toolId) : [...prev, toolId]
    );
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

  const handleCreate = async () => {
    setIsCreating(true);
    setError(null);

    try {
      await agentsApi.createCustomAgent({
        name: name.trim(),
        system_prompt: systemPrompt.trim(),
        tools: selectedTools.map((id) => ({ tool_id: id, config: {} })),
      });
      navigate('/agents');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create agent');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="container max-w-4xl py-8">
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
  );
}
