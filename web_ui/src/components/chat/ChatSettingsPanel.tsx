import { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { useSettingsStore } from '@/stores';
import { modelsApi } from '@/api';
import type { ProviderInfo, ModelInfo } from '@/types/api';

interface ChatSettingsPanelProps {
  className?: string;
  compact?: boolean;
}

/**
 * Settings panel with provider/model/temperature controls.
 * Fetches providers and models from the API.
 */
export function ChatSettingsPanel({ className, compact = false }: ChatSettingsPanelProps) {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const { provider, model, temperature, setProvider, setModel, setTemperature } =
    useSettingsStore();

  // Fetch providers on mount
  useEffect(() => {
    modelsApi.listProviders().then(setProviders).catch(console.error);
  }, []);

  // Fetch available models when provider changes
  useEffect(() => {
    if (provider) {
      modelsApi
        .getProviderDetails(provider)
        .then((details) => {
          setAvailableModels(details.available_models);
        })
        .catch(console.error);
    }
  }, [provider]);

  const availableProvider = providers.find((p) => p.name === provider);

  if (compact) {
    return (
      <Card className={className}>
        <CardContent className="pt-4 pb-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-muted-foreground">Provider</label>
              <Select value={provider} onValueChange={setProvider}>
                <SelectTrigger className="h-8 w-[120px] text-xs">
                  <SelectValue placeholder="Provider" />
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
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-muted-foreground">Model</label>
              <Select
                value={model || 'default'}
                onValueChange={(v) => setModel(v === 'default' ? null : v)}
              >
                <SelectTrigger className="h-8 w-[180px] text-xs">
                  <SelectValue placeholder="Model" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">
                    Default ({availableProvider?.default_model || 'auto'})
                  </SelectItem>
                  {availableModels.map((m) => (
                    <SelectItem key={m.name} value={m.name}>
                      {m.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2 min-w-[150px]">
              <label className="text-xs font-medium text-muted-foreground whitespace-nowrap">
                Temp: {temperature}
              </label>
              <Slider
                value={[temperature]}
                onValueChange={([v]) => setTemperature(v)}
                min={0}
                max={2}
                step={0.1}
                className="w-24"
              />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardContent className="pt-4">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <label className="text-sm font-medium">Provider</label>
            <Select value={provider} onValueChange={setProvider}>
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
          <div className="space-y-2">
            <label className="text-sm font-medium">Model</label>
            <Select
              value={model || 'default'}
              onValueChange={(v) => setModel(v === 'default' ? null : v)}
            >
              <SelectTrigger>
                <SelectValue
                  placeholder={availableProvider?.default_model || 'Default'}
                />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">
                  Default ({availableProvider?.default_model || 'auto'})
                </SelectItem>
                {availableModels.map((m) => (
                  <SelectItem key={m.name} value={m.name}>
                    {m.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">
              Temperature: {temperature}
            </label>
            <Slider
              value={[temperature]}
              onValueChange={([v]) => setTemperature(v)}
              min={0}
              max={2}
              step={0.1}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
