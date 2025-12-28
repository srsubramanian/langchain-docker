import { useEffect, useRef, useState } from 'react';
import { Send, Loader2, Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import { useSessionStore, useSettingsStore } from '@/stores';
import { chatApi, sessionsApi, modelsApi } from '@/api';
import type { ProviderInfo, Message } from '@/types/api';
import { cn } from '@/lib/cn';

export function ChatPage() {
  const [input, setInput] = useState('');
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const {
    sessionId,
    messages,
    isLoading,
    isStreaming,
    streamingContent,
    error,
    setSessionId,
    addMessage,
    setMessages,
    setStreaming,
    setError,
    appendStreamingContent,
    clearStreamingContent,
  } = useSessionStore();

  const { provider, model, temperature, setProvider, setModel, setTemperature } =
    useSettingsStore();

  // Fetch providers on mount
  useEffect(() => {
    modelsApi.listProviders().then(setProviders).catch(console.error);
  }, []);

  // Initialize session
  useEffect(() => {
    if (!sessionId) {
      sessionsApi
        .create({ metadata: { source: 'web_ui' } })
        .then((session) => {
          setSessionId(session.session_id);
          if (session.messages.length > 0) {
            setMessages(session.messages);
          }
        })
        .catch(console.error);
    }
  }, [sessionId, setSessionId, setMessages]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingContent]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading || isStreaming) return;

    const userMessage: Message = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    addMessage(userMessage);
    setInput('');
    setError(null);
    setStreaming(true);
    clearStreamingContent();

    try {
      for await (const event of chatApi.streamMessage({
        message: userMessage.content,
        session_id: sessionId,
        provider,
        model,
        temperature,
      })) {
        if (event.event === 'start') {
          if (event.session_id && !sessionId) {
            setSessionId(event.session_id);
          }
        } else if (event.event === 'token') {
          appendStreamingContent(event.content || '');
        } else if (event.event === 'done') {
          if (event.message) {
            addMessage(event.message);
          }
          clearStreamingContent();
          setStreaming(false);
        } else if (event.event === 'error') {
          setError(event.error || 'An error occurred');
          setStreaming(false);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
      setStreaming(false);
    }
  };

  const availableProvider = providers.find((p) => p.name === provider);

  return (
    <div className="container flex h-[calc(100vh-3.5rem)] flex-col py-4">
      {/* Settings Panel */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="outline">{provider}</Badge>
          {model && <Badge variant="secondary">{model}</Badge>}
          <Badge variant="secondary">temp: {temperature}</Badge>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowSettings(!showSettings)}
        >
          <Settings2 className="mr-2 h-4 w-4" />
          Settings
        </Button>
      </div>

      {showSettings && (
        <Card className="mb-4">
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
                  value={model || ''}
                  onValueChange={(v) => setModel(v || null)}
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={availableProvider?.default_model || 'Default'}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">Default</SelectItem>
                    {/* Models can be loaded from provider details */}
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
      )}

      {/* Messages */}
      <ScrollArea className="flex-1 pr-4" ref={scrollRef}>
        <div className="space-y-4 pb-4">
          {messages.length === 0 && !isStreaming && (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              <p>Start a conversation by sending a message below.</p>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={index}
              className={cn(
                'flex',
                message.role === 'user' ? 'justify-end' : 'justify-start'
              )}
            >
              <div
                className={cn(
                  'max-w-[80%] rounded-lg px-4 py-2',
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                )}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
              </div>
            </div>
          ))}

          {isStreaming && streamingContent && (
            <div className="flex justify-start">
              <div className="max-w-[80%] rounded-lg bg-muted px-4 py-2">
                <p className="whitespace-pre-wrap">{streamingContent}</p>
                <span className="inline-block h-4 w-1 animate-pulse bg-foreground" />
              </div>
            </div>
          )}

          {error && (
            <div className="flex justify-center">
              <div className="rounded-lg bg-destructive/10 px-4 py-2 text-destructive">
                {error}
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <form onSubmit={handleSubmit} className="mt-4 flex gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message..."
          disabled={isLoading || isStreaming}
          className="flex-1"
        />
        <Button type="submit" disabled={isLoading || isStreaming || !input.trim()}>
          {isLoading || isStreaming ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </form>
    </div>
  );
}
