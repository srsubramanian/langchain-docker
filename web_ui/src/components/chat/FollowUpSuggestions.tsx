import { Button } from '@/components/ui/button';
import { cn } from '@/lib/cn';
import type { FollowUpSuggestion } from '@/types/api';

interface FollowUpSuggestionsProps {
  suggestions: FollowUpSuggestion[];
  onSelectSuggestion: (prompt: string) => void;
  className?: string;
}

/**
 * Component to display follow-up suggestions as clickable buttons.
 * These appear after assistant messages to help users continue their investigation.
 */
export function FollowUpSuggestions({
  suggestions,
  onSelectSuggestion,
  className
}: FollowUpSuggestionsProps) {
  if (suggestions.length === 0) {
    return null;
  }

  return (
    <div className={cn('flex flex-wrap gap-2 mt-3', className)}>
      {suggestions.map((suggestion, index) => (
        <Button
          key={index}
          variant="outline"
          size="sm"
          className="h-auto py-1.5 px-3 text-left whitespace-normal text-xs hover:bg-muted/80 transition-colors"
          onClick={() => onSelectSuggestion(suggestion.prompt)}
        >
          <span className="mr-1.5">{suggestion.icon}</span>
          <span>{suggestion.title}</span>
        </Button>
      ))}
    </div>
  );
}
