import { Settings2, Wrench } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useSettingsStore } from '@/stores';
import { useMCPStore } from '@/stores/mcpStore';

interface ChatSettingsBarProps {
  showSettings?: boolean; // Used to indicate active state (optional)
  onToggleSettings: () => void;
  compact?: boolean;
  showMCPBadge?: boolean;
}

/**
 * Settings bar showing current provider/model/temperature badges
 * with a toggle button to show/hide the settings panel.
 */
export function ChatSettingsBar({
  onToggleSettings,
  compact = false,
  showMCPBadge = true,
}: ChatSettingsBarProps) {
  const { provider, model, temperature } = useSettingsStore();
  const { enabledServerIds } = useMCPStore();

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="text-xs">
          {provider}
        </Badge>
        {model && (
          <Badge variant="secondary" className="text-xs">
            {model}
          </Badge>
        )}
        {showMCPBadge && enabledServerIds.length > 0 && (
          <Badge variant="default" className="bg-teal-600 text-xs">
            <Wrench className="mr-1 h-3 w-3" />
            {enabledServerIds.length} MCP
          </Badge>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleSettings}
          className="h-7 px-2"
        >
          <Settings2 className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Badge variant="outline">{provider}</Badge>
        {model && <Badge variant="secondary">{model}</Badge>}
        <Badge variant="secondary">temp: {temperature}</Badge>
        {showMCPBadge && enabledServerIds.length > 0 && (
          <Badge variant="default" className="bg-teal-600">
            <Wrench className="mr-1 h-3 w-3" />
            {enabledServerIds.length} MCP
          </Badge>
        )}
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={onToggleSettings}
      >
        <Settings2 className="mr-2 h-4 w-4" />
        Settings
      </Button>
    </div>
  );
}
