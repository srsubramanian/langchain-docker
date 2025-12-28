import { useState } from 'react';
import {
  Search,
  Calculator,
  Cloud,
  Database,
  TrendingUp,
  Bot,
  Plus,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/cn';
import { agentTemplates, templateCategories, type AgentTemplate } from './templates';

interface TemplateSelectorProps {
  onSelectTemplate: (template: AgentTemplate) => void;
  onStartFromScratch: () => void;
}

// Map icon names to components
const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  Search,
  Calculator,
  Cloud,
  Database,
  TrendingUp,
  Bot,
};

function TemplateCard({
  template,
  onSelect,
}: {
  template: AgentTemplate;
  onSelect: () => void;
}) {
  const Icon = iconMap[template.icon] || Bot;

  return (
    <Card
      className="group cursor-pointer transition-all hover:shadow-lg hover:border-primary/50 hover:scale-[1.02]"
      onClick={onSelect}
    >
      <CardContent className="p-5">
        <div className="flex items-start gap-4">
          {/* Icon */}
          <div
            className={cn(
              'flex h-12 w-12 shrink-0 items-center justify-center rounded-lg text-white',
              template.color
            )}
          >
            <Icon className="h-6 w-6" />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-lg">{template.name}</h3>
            </div>
            <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
              {template.description}
            </p>

            {/* Tools preview */}
            <div className="flex flex-wrap gap-1">
              {template.tools.slice(0, 3).map((tool) => (
                <Badge key={tool} variant="secondary" className="text-xs">
                  {tool.replace(/_/g, ' ')}
                </Badge>
              ))}
              {template.tools.length > 3 && (
                <Badge variant="secondary" className="text-xs">
                  +{template.tools.length - 3} more
                </Badge>
              )}
            </div>
          </div>
        </div>

        {/* Hover indicator */}
        <div className="mt-4 pt-3 border-t opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="text-sm text-primary font-medium">
            Use this template →
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

export function TemplateSelector({
  onSelectTemplate,
  onStartFromScratch,
}: TemplateSelectorProps) {
  const [selectedCategory, setSelectedCategory] = useState('all');

  const filteredTemplates =
    selectedCategory === 'all'
      ? agentTemplates
      : agentTemplates.filter((t) => t.category === selectedCategory);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-2">
        <div className="flex items-center justify-center gap-2">
          <Sparkles className="h-6 w-6 text-primary" />
          <h2 className="text-2xl font-bold">Start with a Template</h2>
        </div>
        <p className="text-muted-foreground max-w-lg mx-auto">
          Choose a pre-configured template to get started quickly, or create your own agent from scratch.
        </p>
      </div>

      {/* Category filter */}
      <div className="flex flex-wrap justify-center gap-2">
        {templateCategories.map((category) => (
          <Button
            key={category.id}
            variant={selectedCategory === category.id ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSelectedCategory(category.id)}
          >
            {category.name}
          </Button>
        ))}
      </div>

      {/* Template grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filteredTemplates.map((template) => (
          <TemplateCard
            key={template.id}
            template={template}
            onSelect={() => onSelectTemplate(template)}
          />
        ))}
      </div>

      {/* Start from scratch option */}
      <div className="flex flex-col items-center gap-4 pt-6 border-t">
        <p className="text-muted-foreground text-sm">
          Want to build something unique?
        </p>
        <Button variant="outline" size="lg" onClick={onStartFromScratch}>
          <Plus className="h-4 w-4 mr-2" />
          Start from Scratch
        </Button>
      </div>
    </div>
  );
}
