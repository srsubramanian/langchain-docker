import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Save,
  Plus,
  Trash2,
  FileText,
  Code,
  Eye,
  Loader2,
  Download,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { skillsApi } from '@/api';
import type { SkillResource, SkillScript } from '@/types/api';

const CATEGORIES = [
  { value: 'general', label: 'General' },
  { value: 'database', label: 'Database' },
  { value: 'document', label: 'Document' },
  { value: 'code', label: 'Code' },
  { value: 'research', label: 'Research' },
  { value: 'analysis', label: 'Analysis' },
];

const LANGUAGES = [
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'bash', label: 'Bash' },
  { value: 'sql', label: 'SQL' },
];

export function SkillEditor() {
  const { skillId } = useParams();
  const navigate = useNavigate();
  const isEditing = !!skillId && skillId !== 'new';
  const isViewing = window.location.pathname.includes('/view');

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('general');
  const [version, setVersion] = useState('1.0.0');
  const [author, setAuthor] = useState('');
  const [coreContent, setCoreContent] = useState('');
  const [resources, setResources] = useState<SkillResource[]>([]);
  const [scripts, setScripts] = useState<SkillScript[]>([]);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('editor');
  const [isBuiltin, setIsBuiltin] = useState(false);

  // Load skill data when editing
  useEffect(() => {
    if (isEditing) {
      loadSkill();
    }
  }, [skillId, isEditing]);

  const loadSkill = async () => {
    if (!skillId) return;
    setIsLoading(true);
    try {
      const skill = await skillsApi.get(skillId);
      setName(skill.name);
      setDescription(skill.description);
      setCategory(skill.category);
      setVersion(skill.version);
      setAuthor(skill.author || '');
      setCoreContent(skill.core_content || '');
      setResources(skill.resources || []);
      setScripts(skill.scripts || []);
      setIsBuiltin(skill.is_builtin);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load skill');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    try {
      if (isEditing) {
        await skillsApi.update(skillId!, {
          name,
          description,
          category,
          version,
          author: author || null,
          core_content: coreContent,
          resources,
          scripts,
        });
      } else {
        await skillsApi.create({
          name,
          description,
          category,
          version,
          author: author || null,
          core_content: coreContent,
          resources,
          scripts,
        });
      }
      navigate('/skills');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save skill');
    } finally {
      setIsSaving(false);
    }
  };

  const handleExport = async () => {
    if (!skillId) return;
    try {
      const result = await skillsApi.export(skillId);
      // Create download
      const blob = new Blob([result.content], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${skillId}-SKILL.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export skill');
    }
  };

  const addResource = () => {
    setResources([...resources, { name: '', description: '', content: '' }]);
  };

  const updateResource = (index: number, updates: Partial<SkillResource>) => {
    setResources(
      resources.map((r, i) => (i === index ? { ...r, ...updates } : r))
    );
  };

  const removeResource = (index: number) => {
    setResources(resources.filter((_, i) => i !== index));
  };

  const addScript = () => {
    setScripts([
      ...scripts,
      { name: '', description: '', language: 'python', content: '' },
    ]);
  };

  const updateScript = (index: number, updates: Partial<SkillScript>) => {
    setScripts(scripts.map((s, i) => (i === index ? { ...s, ...updates } : s)));
  };

  const removeScript = (index: number) => {
    setScripts(scripts.filter((_, i) => i !== index));
  };

  const generateSkillMd = () => {
    const frontmatter = `---
name: ${name}
description: ${description}
category: ${category}
version: ${version}${author ? `\nauthor: ${author}` : ''}
---`;
    return `${frontmatter}\n\n${coreContent}`;
  };

  const canSave = name.trim().length >= 1 && description.trim().length >= 10 && coreContent.trim().length >= 10;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-3.5rem)]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="container max-w-5xl py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/skills')}
            className="gap-1"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold">
              {isViewing ? 'View Skill' : isEditing ? 'Edit Skill' : 'Create Skill'}
            </h1>
            {isBuiltin && (
              <Badge variant="outline" className="mt-1">
                Built-in (Read Only)
              </Badge>
            )}
          </div>
        </div>

        <div className="flex gap-2">
          {isEditing && !isBuiltin && (
            <Button variant="outline" onClick={handleExport} className="gap-2">
              <Download className="h-4 w-4" />
              Export
            </Button>
          )}
          {!isBuiltin && !isViewing && (
            <Button onClick={handleSave} disabled={isSaving || !canSave} className="gap-2">
              {isSaving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {isEditing ? 'Save Changes' : 'Create Skill'}
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg bg-destructive/10 px-4 py-3 text-destructive">
          {error}
        </div>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="editor" className="gap-2">
            <FileText className="h-4 w-4" />
            Editor
          </TabsTrigger>
          <TabsTrigger value="resources" className="gap-2">
            <FileText className="h-4 w-4" />
            Resources ({resources.length})
          </TabsTrigger>
          <TabsTrigger value="scripts" className="gap-2">
            <Code className="h-4 w-4" />
            Scripts ({scripts.length})
          </TabsTrigger>
          <TabsTrigger value="preview" className="gap-2">
            <Eye className="h-4 w-4" />
            Preview
          </TabsTrigger>
        </TabsList>

        {/* Editor Tab */}
        <TabsContent value="editor">
          <div className="grid gap-6">
            {/* Metadata */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Skill Metadata (Level 1)</CardTitle>
                <p className="text-sm text-muted-foreground">
                  This information is always loaded in the agent's system prompt.
                </p>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Name *</label>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="My Custom Skill"
                    disabled={isBuiltin}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Category</label>
                  <Select value={category} onValueChange={setCategory} disabled={isBuiltin}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CATEGORIES.map((cat) => (
                        <SelectItem key={cat.value} value={cat.value}>
                          {cat.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2 md:col-span-2">
                  <label className="text-sm font-medium">Description * (min 10 chars)</label>
                  <Textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="A brief description of what this skill does..."
                    className="min-h-[80px]"
                    disabled={isBuiltin}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Version</label>
                  <Input
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                    placeholder="1.0.0"
                    disabled={isBuiltin}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Author</label>
                  <Input
                    value={author}
                    onChange={(e) => setAuthor(e.target.value)}
                    placeholder="Your name"
                    disabled={isBuiltin}
                  />
                </div>
              </CardContent>
            </Card>

            {/* Core Content */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Core Instructions (Level 2)</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Main skill instructions loaded when the skill is triggered. Use Markdown format.
                </p>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={coreContent}
                  onChange={(e) => setCoreContent(e.target.value)}
                  placeholder={`## Instructions

When this skill is activated, follow these steps:

1. First, understand the user's request
2. Then, apply the appropriate technique
3. Finally, provide a clear response

### Guidelines
- Be thorough and accurate
- Explain your reasoning
- Ask for clarification if needed`}
                  className="min-h-[300px] font-mono text-sm"
                  disabled={isBuiltin}
                />
                <p className="mt-2 text-xs text-muted-foreground">
                  {coreContent.length} characters (minimum 10)
                </p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Resources Tab */}
        <TabsContent value="resources">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base">Additional Resources (Level 3)</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Optional files that agents can load on-demand for detailed guidance.
                </p>
              </div>
              {!isBuiltin && (
                <Button onClick={addResource} size="sm" className="gap-2">
                  <Plus className="h-4 w-4" />
                  Add Resource
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {resources.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No resources added yet. Resources are loaded only when needed.
                </div>
              ) : (
                <div className="space-y-4">
                  {resources.map((resource, index) => (
                    <Card key={index}>
                      <CardContent className="pt-4">
                        <div className="flex gap-4 mb-4">
                          <div className="flex-1 space-y-2">
                            <label className="text-sm font-medium">Filename</label>
                            <Input
                              value={resource.name}
                              onChange={(e) =>
                                updateResource(index, { name: e.target.value })
                              }
                              placeholder="examples.md"
                              disabled={isBuiltin}
                            />
                          </div>
                          <div className="flex-1 space-y-2">
                            <label className="text-sm font-medium">Description</label>
                            <Input
                              value={resource.description}
                              onChange={(e) =>
                                updateResource(index, { description: e.target.value })
                              }
                              placeholder="Example usage patterns"
                              disabled={isBuiltin}
                            />
                          </div>
                          {!isBuiltin && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => removeResource(index)}
                              className="mt-7"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                        <div className="space-y-2">
                          <label className="text-sm font-medium">Content</label>
                          <Textarea
                            value={resource.content || ''}
                            onChange={(e) =>
                              updateResource(index, { content: e.target.value })
                            }
                            placeholder="Resource content in markdown..."
                            className="min-h-[150px] font-mono text-sm"
                            disabled={isBuiltin}
                          />
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Scripts Tab */}
        <TabsContent value="scripts">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base">Bundled Scripts</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Executable scripts that agents can run for deterministic operations.
                </p>
              </div>
              {!isBuiltin && (
                <Button onClick={addScript} size="sm" className="gap-2">
                  <Plus className="h-4 w-4" />
                  Add Script
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {scripts.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No scripts added yet. Scripts provide deterministic tool execution.
                </div>
              ) : (
                <div className="space-y-4">
                  {scripts.map((script, index) => (
                    <Card key={index}>
                      <CardContent className="pt-4">
                        <div className="flex gap-4 mb-4">
                          <div className="flex-1 space-y-2">
                            <label className="text-sm font-medium">Filename</label>
                            <Input
                              value={script.name}
                              onChange={(e) =>
                                updateScript(index, { name: e.target.value })
                              }
                              placeholder="extract.py"
                              disabled={isBuiltin}
                            />
                          </div>
                          <div className="flex-1 space-y-2">
                            <label className="text-sm font-medium">Language</label>
                            <Select
                              value={script.language}
                              onValueChange={(value) =>
                                updateScript(index, { language: value })
                              }
                              disabled={isBuiltin}
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {LANGUAGES.map((lang) => (
                                  <SelectItem key={lang.value} value={lang.value}>
                                    {lang.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          {!isBuiltin && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => removeScript(index)}
                              className="mt-7"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                        <div className="space-y-2 mb-4">
                          <label className="text-sm font-medium">Description</label>
                          <Input
                            value={script.description}
                            onChange={(e) =>
                              updateScript(index, { description: e.target.value })
                            }
                            placeholder="What this script does"
                            disabled={isBuiltin}
                          />
                        </div>
                        <div className="space-y-2">
                          <label className="text-sm font-medium">Code</label>
                          <Textarea
                            value={script.content || ''}
                            onChange={(e) =>
                              updateScript(index, { content: e.target.value })
                            }
                            placeholder="# Your code here..."
                            className="min-h-[200px] font-mono text-sm"
                            disabled={isBuiltin}
                          />
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Preview Tab */}
        <TabsContent value="preview">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">SKILL.md Preview</CardTitle>
              <p className="text-sm text-muted-foreground">
                This is how your skill will look in the portable SKILL.md format.
              </p>
            </CardHeader>
            <CardContent>
              <pre className="p-4 bg-muted rounded-lg overflow-x-auto text-sm font-mono whitespace-pre-wrap">
                {generateSkillMd()}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
