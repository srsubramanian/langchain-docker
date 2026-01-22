import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/cn';
import type { StarterPromptCategory, StarterPrompt } from '@/types/api';

interface StarterPromptsProps {
  categories: StarterPromptCategory[];
  onSelectPrompt: (prompt: string) => void;
  className?: string;
}

/**
 * Component to display categorized starter prompts for an agent.
 * Prompts containing {url} will show a dialog to enter the URL.
 */
export function StarterPrompts({ categories, onSelectPrompt, className }: StarterPromptsProps) {
  const [urlDialogOpen, setUrlDialogOpen] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const [urlInput, setUrlInput] = useState('');

  const handlePromptClick = useCallback((prompt: StarterPrompt) => {
    if (prompt.prompt.includes('{url}')) {
      // Show URL input dialog
      setPendingPrompt(prompt.prompt);
      setUrlInput('');
      setUrlDialogOpen(true);
    } else {
      // Send prompt directly
      onSelectPrompt(prompt.prompt);
    }
  }, [onSelectPrompt]);

  const handleUrlSubmit = useCallback(() => {
    if (pendingPrompt && urlInput.trim()) {
      // Replace {url} placeholder with actual URL
      const finalPrompt = pendingPrompt.replace('{url}', urlInput.trim());
      onSelectPrompt(finalPrompt);
      setUrlDialogOpen(false);
      setPendingPrompt(null);
      setUrlInput('');
    }
  }, [pendingPrompt, urlInput, onSelectPrompt]);

  if (categories.length === 0) {
    return null;
  }

  return (
    <div className={cn('space-y-6', className)}>
      <div className="text-center mb-4">
        <h3 className="text-lg font-medium text-foreground mb-1">
          What would you like to analyze?
        </h3>
        <p className="text-sm text-muted-foreground">
          Choose a starter prompt or type your own question below
        </p>
      </div>

      {categories.map((category) => (
        <div key={category.category} className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <span>{category.icon}</span>
            <span>{category.category}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {category.prompts.map((prompt, index) => (
              <Button
                key={index}
                variant="outline"
                size="sm"
                className="h-auto py-2 px-3 text-left whitespace-normal"
                onClick={() => handlePromptClick(prompt)}
              >
                <span className="mr-2">{prompt.icon}</span>
                <span>{prompt.title}</span>
              </Button>
            ))}
          </div>
        </div>
      ))}

      {/* URL Input Dialog */}
      <Dialog open={urlDialogOpen} onOpenChange={setUrlDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Enter URL to analyze</DialogTitle>
            <DialogDescription>
              Enter the website URL you want to analyze.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Input
              placeholder="https://example.com"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleUrlSubmit();
                }
              }}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUrlDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUrlSubmit} disabled={!urlInput.trim()}>
              Analyze
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
