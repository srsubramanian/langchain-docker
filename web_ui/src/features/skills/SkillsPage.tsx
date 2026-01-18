import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus,
  Search,
  BookOpen,
  Database,
  FileText,
  Code,
  Sparkles,
  Trash2,
  Edit,
  Eye,
  Lock,
  GitBranch,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { skillsApi } from '@/api';
import type { SkillMetadata } from '@/types/api';
import { cn } from '@/lib/cn';

// Map categories to icons
const categoryIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  database: Database,
  document: FileText,
  code: Code,
  general: Sparkles,
};

// Map categories to colors
const categoryColors: Record<string, string> = {
  database: 'bg-purple-500',
  document: 'bg-blue-500',
  code: 'bg-green-500',
  general: 'bg-orange-500',
};

interface SkillWithVersion extends SkillMetadata {
  is_builtin?: boolean;
  version_count?: number;
}

function SkillCard({
  skill,
  onView,
  onEdit,
  onDelete,
}: {
  skill: SkillWithVersion;
  onView: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const Icon = categoryIcons[skill.category] || BookOpen;
  const color = categoryColors[skill.category] || 'bg-primary';
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleDelete = () => {
    if (showDeleteConfirm) {
      onDelete();
      setShowDeleteConfirm(false);
    } else {
      setShowDeleteConfirm(true);
      setTimeout(() => setShowDeleteConfirm(false), 3000);
    }
  };

  return (
    <Card className="group hover:shadow-lg transition-shadow">
      <CardContent className="p-5">
        <div className="flex items-start gap-4">
          {/* Icon */}
          <div
            className={cn(
              'flex h-12 w-12 shrink-0 items-center justify-center rounded-lg text-white',
              color
            )}
          >
            <Icon className="h-6 w-6" />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-lg">{skill.name}</h3>
              {skill.is_builtin && (
                <Badge variant="outline" className="text-xs gap-1">
                  <Lock className="h-3 w-3" />
                  Built-in
                </Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
              {skill.description}
            </p>

            {/* Metadata */}
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary" className="text-xs">
                {skill.category}
              </Badge>
              <Badge variant="outline" className="text-xs">
                v{skill.version}
              </Badge>
              {skill.version_count && skill.version_count > 1 && (
                <Badge variant="outline" className="text-xs gap-1">
                  <GitBranch className="h-3 w-3" />
                  {skill.version_count} versions
                </Badge>
              )}
              {skill.author && (
                <Badge variant="outline" className="text-xs">
                  by {skill.author}
                </Badge>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button
              variant="ghost"
              size="icon"
              onClick={onView}
              title="View skill"
            >
              <Eye className="h-4 w-4" />
            </Button>
            {!skill.is_builtin && (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onEdit}
                  title="Edit skill"
                >
                  <Edit className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleDelete}
                  className={cn(
                    showDeleteConfirm && 'text-destructive hover:text-destructive'
                  )}
                  title={showDeleteConfirm ? 'Click again to confirm' : 'Delete skill'}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function SkillsPage() {
  const navigate = useNavigate();
  const [skills, setSkills] = useState<SkillWithVersion[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');

  // Fetch skills
  useEffect(() => {
    loadSkills();
  }, []);

  const loadSkills = async () => {
    setIsLoading(true);
    try {
      const response = await skillsApi.list();
      // Fetch full details to get is_builtin flag and version info
      const fullSkills = await Promise.all(
        response.skills.map(async (s) => {
          try {
            // Try to get versioned info first (includes version_count)
            const versioned = await skillsApi.getVersioned(s.id);
            return {
              ...s,
              is_builtin: versioned.is_builtin,
              version_count: versioned.version_count,
            };
          } catch {
            // Fall back to basic get
            try {
              const full = await skillsApi.get(s.id);
              return { ...s, is_builtin: full.is_builtin };
            } catch {
              return { ...s, is_builtin: false };
            }
          }
        })
      );
      setSkills(fullSkills);
    } catch (error) {
      console.error('Failed to load skills:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (skillId: string) => {
    try {
      await skillsApi.delete(skillId);
      setSkills((prev) => prev.filter((s) => s.id !== skillId));
    } catch (error) {
      console.error('Failed to delete skill:', error);
    }
  };

  // Filter skills
  const filteredSkills = skills.filter((skill) => {
    // Tab filter
    if (activeTab === 'builtin' && !skill.is_builtin) return false;
    if (activeTab === 'custom' && skill.is_builtin) return false;

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        skill.name.toLowerCase().includes(query) ||
        skill.description.toLowerCase().includes(query) ||
        skill.category.toLowerCase().includes(query)
      );
    }
    return true;
  });

  const builtinCount = skills.filter((s) => s.is_builtin).length;
  const customCount = skills.filter((s) => !s.is_builtin).length;

  return (
    <div className="container max-w-6xl py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Sparkles className="h-8 w-8 text-primary" />
            Agent Skills
          </h1>
          <p className="text-muted-foreground mt-1">
            Create and manage skills that extend agent capabilities with progressive disclosure.
          </p>
        </div>
        <Button onClick={() => navigate('/skills/new')} className="gap-2">
          <Plus className="h-4 w-4" />
          Create Skill
        </Button>
      </div>

      {/* Progressive Disclosure Info */}
      <Card className="mb-6 bg-muted/50">
        <CardContent className="p-4">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <BookOpen className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-medium mb-1">Progressive Disclosure Pattern</h3>
              <p className="text-sm text-muted-foreground">
                Skills load context in three levels: <strong>Level 1</strong> (metadata) is always in the agent prompt,{' '}
                <strong>Level 2</strong> (core instructions) loads when triggered, and{' '}
                <strong>Level 3</strong> (detailed resources) loads only as needed.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs and Search */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-6">
        <div className="flex items-center justify-between gap-4">
          <TabsList>
            <TabsTrigger value="all">All Skills ({skills.length})</TabsTrigger>
            <TabsTrigger value="builtin">Built-in ({builtinCount})</TabsTrigger>
            <TabsTrigger value="custom">Custom ({customCount})</TabsTrigger>
          </TabsList>

          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search skills..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        <TabsContent value="all" className="mt-6">
          <SkillGrid
            skills={filteredSkills}
            isLoading={isLoading}
            onView={(id) => navigate(`/skills/${id}`)}
            onEdit={(id) => navigate(`/skills/${id}/edit`)}
            onDelete={handleDelete}
          />
        </TabsContent>

        <TabsContent value="builtin" className="mt-6">
          <SkillGrid
            skills={filteredSkills}
            isLoading={isLoading}
            onView={(id) => navigate(`/skills/${id}`)}
            onEdit={(id) => navigate(`/skills/${id}/edit`)}
            onDelete={handleDelete}
          />
        </TabsContent>

        <TabsContent value="custom" className="mt-6">
          {customCount === 0 && !searchQuery ? (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Sparkles className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="font-semibold text-lg mb-2">No custom skills yet</h3>
                <p className="text-muted-foreground text-center mb-4 max-w-md">
                  Create your first skill to extend agent capabilities with custom instructions,
                  resources, and scripts.
                </p>
                <Button onClick={() => navigate('/skills/new')} className="gap-2">
                  <Plus className="h-4 w-4" />
                  Create Your First Skill
                </Button>
              </CardContent>
            </Card>
          ) : (
            <SkillGrid
              skills={filteredSkills}
              isLoading={isLoading}
              onView={(id) => navigate(`/skills/${id}`)}
              onEdit={(id) => navigate(`/skills/${id}/edit`)}
              onDelete={handleDelete}
            />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SkillGrid({
  skills,
  isLoading,
  onView,
  onEdit,
  onDelete,
}: {
  skills: SkillWithVersion[];
  isLoading: boolean;
  onView: (id: string) => void;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="p-5">
              <div className="flex items-start gap-4">
                <div className="h-12 w-12 rounded-lg bg-muted" />
                <div className="flex-1">
                  <div className="h-5 w-32 bg-muted rounded mb-2" />
                  <div className="h-4 w-full bg-muted rounded mb-3" />
                  <div className="flex gap-2">
                    <div className="h-5 w-16 bg-muted rounded" />
                    <div className="h-5 w-12 bg-muted rounded" />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (skills.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No skills found matching your search.
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {skills.map((skill) => (
        <SkillCard
          key={skill.id}
          skill={skill}
          onView={() => onView(skill.id)}
          onEdit={() => onEdit(skill.id)}
          onDelete={() => onDelete(skill.id)}
        />
      ))}
    </div>
  );
}
