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
  History,
  BarChart3,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Pencil,
  X,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { skillsApi } from '@/api';
import type { SkillResource, SkillScript, SkillToolConfig, SkillResourceConfig } from '@/types/api';
import { VersionHistory } from './VersionHistory';
import { SkillMetricsPanel } from './SkillMetricsPanel';
import { MarkdownRenderer } from '@/components/ui/markdown-renderer';
import { Wrench, Database } from 'lucide-react';

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
  // View mode: when editing an existing skill but not on the /edit route
  const isViewing = isEditing && !window.location.pathname.endsWith('/edit');

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('general');
  const [version, setVersion] = useState('1.0.0');
  const [author, setAuthor] = useState('');
  const [coreContent, setCoreContent] = useState('');
  const [resources, setResources] = useState<SkillResource[]>([]);
  const [scripts, setScripts] = useState<SkillScript[]>([]);
  const [toolConfigs, setToolConfigs] = useState<SkillToolConfig[]>([]);
  const [resourceConfigs, setResourceConfigs] = useState<SkillResourceConfig[]>([]);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('editor');
  const [isBuiltin, setIsBuiltin] = useState(false);
  const [hasCustomContent, setHasCustomContent] = useState(false);

  // Version save dialog state
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [changeSummary, setChangeSummary] = useState('');

  // Preview mode: 'rendered' or 'raw'
  const [previewMode, setPreviewMode] = useState<'rendered' | 'raw'>('rendered');

  // Resource expansion state (for built-in skills)
  const [expandedResources, setExpandedResources] = useState<Set<string>>(new Set());
  const [resourceContents, setResourceContents] = useState<Record<string, string>>({});
  const [loadingResources, setLoadingResources] = useState<Set<string>>(new Set());

  // Resource editing state (for built-in skills)
  const [editingResources, setEditingResources] = useState<Set<string>>(new Set());
  const [editedResourceContents, setEditedResourceContents] = useState<Record<string, string>>({});

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
      setToolConfigs(skill.tool_configs || []);
      setResourceConfigs(skill.resource_configs || []);
      setIsBuiltin(skill.is_builtin);
      setHasCustomContent(skill.has_custom_content || false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load skill');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveClick = () => {
    if (isEditing) {
      // Show dialog to enter change summary for version history
      setShowSaveDialog(true);
    } else {
      // For new skills, save directly
      performSave();
    }
  };

  const performSave = async () => {
    setIsSaving(true);
    setError(null);
    setShowSaveDialog(false);
    try {
      if (isEditing) {
        // For built-in skills, include any modified resources
        const resourcesToSave = isBuiltin ? getModifiedResources() : resources;

        await skillsApi.update(skillId!, {
          name,
          description,
          category,
          version,
          author: author || null,
          core_content: coreContent,
          resources: resourcesToSave,
          scripts,
          change_summary: changeSummary || null,
        });
        // For built-in skills, stay on page and update state
        if (isBuiltin) {
          setHasCustomContent(true);
          setChangeSummary('');
          // Clear editing state
          setEditingResources(new Set());
          setEditedResourceContents({});
          // Reload to get fresh data
          await loadSkill();
          return;
        }
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
      setChangeSummary('');
      navigate('/skills');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save skill');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    if (!skillId || !isBuiltin) return;

    setIsResetting(true);
    setError(null);
    try {
      await skillsApi.reset(skillId);
      setHasCustomContent(false);
      // Reload to get original file-based content
      await loadSkill();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset skill');
    } finally {
      setIsResetting(false);
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

  // Toggle resource expansion and load content if needed
  const toggleResourceExpansion = async (resourceName: string) => {
    const newExpanded = new Set(expandedResources);

    if (newExpanded.has(resourceName)) {
      // Collapse
      newExpanded.delete(resourceName);
      setExpandedResources(newExpanded);
    } else {
      // Expand
      newExpanded.add(resourceName);
      setExpandedResources(newExpanded);

      // Load content if not already loaded
      if (!resourceContents[resourceName] && skillId) {
        setLoadingResources(prev => new Set(prev).add(resourceName));
        try {
          const result = await skillsApi.loadResource(skillId, resourceName);
          setResourceContents(prev => ({ ...prev, [resourceName]: result.content }));
        } catch (err) {
          setResourceContents(prev => ({
            ...prev,
            [resourceName]: `Error loading resource: ${err instanceof Error ? err.message : 'Unknown error'}`
          }));
        } finally {
          setLoadingResources(prev => {
            const next = new Set(prev);
            next.delete(resourceName);
            return next;
          });
        }
      }
    }
  };

  // Start editing a resource
  const startEditingResource = (resourceName: string) => {
    const content = resourceContents[resourceName] || '';
    setEditedResourceContents(prev => ({ ...prev, [resourceName]: content }));
    setEditingResources(prev => new Set(prev).add(resourceName));
  };

  // Cancel editing a resource
  const cancelEditingResource = (resourceName: string) => {
    setEditingResources(prev => {
      const next = new Set(prev);
      next.delete(resourceName);
      return next;
    });
    setEditedResourceContents(prev => {
      const next = { ...prev };
      delete next[resourceName];
      return next;
    });
  };

  // Save edited resource content (applies to local state, saved with skill)
  const saveResourceEdit = (resourceName: string) => {
    const editedContent = editedResourceContents[resourceName];
    if (editedContent !== undefined) {
      setResourceContents(prev => ({ ...prev, [resourceName]: editedContent }));
    }
    setEditingResources(prev => {
      const next = new Set(prev);
      next.delete(resourceName);
      return next;
    });
  };

  // Check if there are any modified resources
  const getModifiedResources = () => {
    const modified: Array<{ name: string; description: string; content: string }> = [];
    for (const [name, content] of Object.entries(resourceContents)) {
      // Find the resource config for description
      const config = resourceConfigs.find(r => r.name === name);
      if (config && !config.dynamic) {
        modified.push({
          name,
          description: config.description || '',
          content,
        });
      }
    }
    return modified;
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
              <Badge variant={hasCustomContent ? 'default' : 'outline'} className="mt-1">
                {hasCustomContent ? 'Built-in (Customized)' : 'Built-in'}
              </Badge>
            )}
          </div>
        </div>

        <div className="flex gap-2">
          {/* Reset button for built-in skills with custom content */}
          {isBuiltin && hasCustomContent && !isViewing && (
            <Button
              variant="outline"
              onClick={handleReset}
              disabled={isResetting}
              className="gap-2"
            >
              {isResetting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RotateCcw className="h-4 w-4" />
              )}
              Reset to Default
            </Button>
          )}
          {isEditing && !isBuiltin && (
            <Button variant="outline" onClick={handleExport} className="gap-2">
              <Download className="h-4 w-4" />
              Export
            </Button>
          )}
          {/* Save button - shown for both built-in and custom skills */}
          {!isViewing && (
            <Button onClick={handleSaveClick} disabled={isSaving || !canSave} className="gap-2">
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
        <TabsList className="mb-6 flex-wrap">
          <TabsTrigger value="editor" className="gap-2">
            <FileText className="h-4 w-4" />
            Editor
          </TabsTrigger>
          {isBuiltin && toolConfigs.length > 0 && (
            <TabsTrigger value="tools" className="gap-2">
              <Wrench className="h-4 w-4" />
              Tools ({toolConfigs.length})
            </TabsTrigger>
          )}
          <TabsTrigger value="resources" className="gap-2">
            <Database className="h-4 w-4" />
            Resources ({isBuiltin ? resourceConfigs.length : resources.length})
          </TabsTrigger>
          <TabsTrigger value="scripts" className="gap-2">
            <Code className="h-4 w-4" />
            Scripts ({scripts.length})
          </TabsTrigger>
          <TabsTrigger value="preview" className="gap-2">
            <Eye className="h-4 w-4" />
            Preview
          </TabsTrigger>
          {isEditing && (
            <>
              <TabsTrigger value="history" className="gap-2">
                <History className="h-4 w-4" />
                Version History
              </TabsTrigger>
              <TabsTrigger value="metrics" className="gap-2">
                <BarChart3 className="h-4 w-4" />
                Usage Metrics
              </TabsTrigger>
            </>
          )}
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
                {isBuiltin && (
                  <p className="text-sm text-muted-foreground mt-1">
                    <span className="text-primary font-medium">Note:</span> You can customize the instructions for this built-in skill.
                    Dynamic content (database schema, etc.) is preserved. Use "Reset to Default" to restore original content.
                  </p>
                )}
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
                />
                <p className="mt-2 text-xs text-muted-foreground">
                  {coreContent.length} characters (minimum 10)
                </p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Tools Tab (Built-in skills only) */}
        {isBuiltin && toolConfigs.length > 0 && (
          <TabsContent value="tools">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Available Tools</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Tools provided by this skill. Some tools require the skill to be loaded first.
                </p>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {toolConfigs.map((tool, index) => (
                    <Card key={index}>
                      <CardContent className="pt-4">
                        <div className="flex items-start justify-between mb-3">
                          <div>
                            <div className="flex items-center gap-2">
                              <code className="text-sm font-semibold bg-muted px-2 py-0.5 rounded">
                                {tool.name}
                              </code>
                              {tool.requires_skill_loaded && (
                                <Badge variant="outline" className="text-xs">
                                  Requires Skill Loaded
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground mt-1">
                              {tool.description}
                            </p>
                          </div>
                          <Badge variant="secondary" className="text-xs">
                            {tool.method}
                          </Badge>
                        </div>
                        {tool.args && tool.args.length > 0 && (
                          <div className="mt-3 border-t pt-3">
                            <p className="text-xs font-medium text-muted-foreground mb-2">Arguments</p>
                            <div className="space-y-2">
                              {tool.args.map((arg, argIndex) => (
                                <div key={argIndex} className="flex items-start gap-2 text-sm">
                                  <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
                                    {arg.name}
                                  </code>
                                  <span className="text-muted-foreground text-xs">
                                    ({arg.type})
                                  </span>
                                  {arg.required && (
                                    <Badge variant="destructive" className="text-xs h-4">
                                      required
                                    </Badge>
                                  )}
                                  {arg.description && (
                                    <span className="text-xs text-muted-foreground">
                                      - {arg.description}
                                    </span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}

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
              {/* Built-in skills: show resourceConfigs with expandable content */}
              {isBuiltin ? (
                resourceConfigs.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No resources available for this skill.
                  </div>
                ) : (
                  <div className="space-y-4">
                    {resourceConfigs.map((resource, index) => {
                      const isExpanded = expandedResources.has(resource.name);
                      const isLoadingContent = loadingResources.has(resource.name);
                      const content = resourceContents[resource.name];

                      return (
                        <Card key={index}>
                          <CardContent className="pt-4">
                            <div
                              className="flex items-start justify-between cursor-pointer"
                              onClick={() => toggleResourceExpansion(resource.name)}
                            >
                              <div className="flex-1">
                                <div className="flex items-center gap-2">
                                  <code className="text-sm font-semibold bg-muted px-2 py-0.5 rounded">
                                    {resource.name}
                                  </code>
                                  {resource.dynamic && (
                                    <Badge variant="outline" className="text-xs">
                                      Dynamic
                                    </Badge>
                                  )}
                                  {resource.file && (
                                    <Badge variant="secondary" className="text-xs">
                                      {resource.file}
                                    </Badge>
                                  )}
                                </div>
                                <p className="text-sm text-muted-foreground mt-1">
                                  {resource.description}
                                </p>
                                {resource.method && (
                                  <p className="text-xs text-muted-foreground mt-1">
                                    <span className="font-medium">Method:</span>{' '}
                                    <code className="bg-muted px-1 rounded">{resource.method}</code>
                                  </p>
                                )}
                              </div>
                              <Button variant="ghost" size="sm" className="ml-2">
                                {isLoadingContent ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : isExpanded ? (
                                  <ChevronUp className="h-4 w-4" />
                                ) : (
                                  <ChevronDown className="h-4 w-4" />
                                )}
                              </Button>
                            </div>

                            {/* Expanded content */}
                            {isExpanded && (
                              <div className="mt-4 pt-4 border-t">
                                {isLoadingContent ? (
                                  <div className="flex items-center justify-center py-8">
                                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                  </div>
                                ) : content ? (
                                  <div>
                                    {/* Edit controls for non-dynamic resources */}
                                    {!resource.dynamic && !isViewing && (
                                      <div className="flex justify-end mb-2 gap-2">
                                        {editingResources.has(resource.name) ? (
                                          <>
                                            <Button
                                              variant="outline"
                                              size="sm"
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                cancelEditingResource(resource.name);
                                              }}
                                              className="gap-1"
                                            >
                                              <X className="h-3 w-3" />
                                              Cancel
                                            </Button>
                                            <Button
                                              size="sm"
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                saveResourceEdit(resource.name);
                                              }}
                                              className="gap-1"
                                            >
                                              <Save className="h-3 w-3" />
                                              Apply
                                            </Button>
                                          </>
                                        ) : (
                                          <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              startEditingResource(resource.name);
                                            }}
                                            className="gap-1"
                                          >
                                            <Pencil className="h-3 w-3" />
                                            Edit
                                          </Button>
                                        )}
                                      </div>
                                    )}
                                    {resource.dynamic && (
                                      <p className="text-xs text-muted-foreground mb-2 italic">
                                        Dynamic resources are generated at runtime and cannot be edited.
                                      </p>
                                    )}
                                    {/* Content display or editor */}
                                    {editingResources.has(resource.name) ? (
                                      <Textarea
                                        value={editedResourceContents[resource.name] || ''}
                                        onChange={(e) =>
                                          setEditedResourceContents(prev => ({
                                            ...prev,
                                            [resource.name]: e.target.value
                                          }))
                                        }
                                        className="min-h-[400px] font-mono text-sm"
                                        placeholder="Resource content in markdown..."
                                      />
                                    ) : (
                                      <div className="rounded-lg border bg-card p-4 max-h-[500px] overflow-y-auto">
                                        <MarkdownRenderer content={content} />
                                      </div>
                                    )}
                                  </div>
                                ) : (
                                  <div className="text-center py-4 text-muted-foreground">
                                    Click to load resource content
                                  </div>
                                )}
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                )
              ) : (
                /* Custom skills: show editable resources */
                resources.length === 0 ? (
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
                              />
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => removeResource(index)}
                              className="mt-7"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
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
                            />
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )
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
            <CardHeader className="flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base">SKILL.md Preview</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {previewMode === 'rendered'
                    ? 'Rendered markdown with syntax highlighting.'
                    : 'Raw SKILL.md content in portable format.'}
                </p>
              </div>
              <div className="flex gap-1 rounded-lg border p-1">
                <Button
                  variant={previewMode === 'rendered' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setPreviewMode('rendered')}
                  className="gap-1.5"
                >
                  <Eye className="h-4 w-4" />
                  Rendered
                </Button>
                <Button
                  variant={previewMode === 'raw' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setPreviewMode('raw')}
                  className="gap-1.5"
                >
                  <Code className="h-4 w-4" />
                  Raw
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {previewMode === 'rendered' ? (
                <div className="rounded-lg border bg-card p-6">
                  <MarkdownRenderer content={generateSkillMd()} />
                </div>
              ) : (
                <pre className="p-4 bg-muted rounded-lg overflow-x-auto text-sm font-mono whitespace-pre-wrap">
                  {generateSkillMd()}
                </pre>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Version History Tab */}
        {isEditing && (
          <TabsContent value="history">
            <VersionHistory skillId={skillId!} isBuiltin={isBuiltin} />
          </TabsContent>
        )}

        {/* Usage Metrics Tab */}
        {isEditing && (
          <TabsContent value="metrics">
            <SkillMetricsPanel skillId={skillId!} isBuiltin={isBuiltin} />
          </TabsContent>
        )}
      </Tabs>

      {/* Save Version Dialog */}
      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save New Version</DialogTitle>
            <DialogDescription>
              Describe what changed in this version. This helps track the skill's evolution.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Input
              placeholder="What changed? (e.g., 'Improved SQL formatting rules')"
              value={changeSummary}
              onChange={(e) => setChangeSummary(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSaveDialog(false)}>
              Cancel
            </Button>
            <Button onClick={performSave} disabled={isSaving}>
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save Version
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
