// Chat types
export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
  metadata?: Record<string, unknown>;
}

export interface ChatRequest {
  message: string;
  session_id?: string | null;
  provider?: string;
  model?: string | null;
  temperature?: number;
  stream?: boolean;
  max_tokens?: number | null;
  enable_memory?: boolean;
}

export interface MemoryMetadata {
  summarized: boolean;
  summary_triggered: boolean;
  total_messages: number;
  summarized_message_count: number;
  recent_message_count: number;
  summary_content?: string | null;
}

export interface ChatResponse {
  session_id: string;
  message: Message;
  conversation_length: number;
  created_at: string;
  memory_metadata?: MemoryMetadata | null;
}

// SSE Stream events
export interface StreamEvent {
  event: 'start' | 'token' | 'done' | 'error';
  session_id?: string;
  model?: string;
  provider?: string;
  content?: string;
  message?: Message;
  conversation_length?: number;
  memory_metadata?: MemoryMetadata;
  error?: string;
}

// Session types
export interface SessionCreate {
  metadata?: Record<string, unknown>;
}

export interface SessionSummary {
  session_id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message?: string | null;
  metadata: Record<string, unknown>;
}

export interface SessionResponse {
  session_id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  messages: Message[];
  metadata: Record<string, unknown>;
}

export interface SessionList {
  sessions: SessionSummary[];
  total: number;
  limit: number;
  offset: number;
}

// Model types
export interface ProviderInfo {
  name: string;
  available: boolean;
  configured: boolean;
  default_model: string;
}

export interface ModelInfo {
  name: string;
  description: string;
}

export interface ProviderDetails {
  name: string;
  configured: boolean;
  available_models: ModelInfo[];
  default_model: string;
}

// Agent types
export interface AgentInfo {
  name: string;
  description: string;
  tools: string[];
}

export interface ToolParameter {
  name: string;
  type: 'string' | 'number' | 'boolean';
  description: string;
  default?: unknown;
  required: boolean;
}

export interface ToolTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  parameters: ToolParameter[];
}

export interface ToolConfig {
  tool_id: string;
  config: Record<string, unknown>;
}

export interface CustomAgentInfo {
  id: string;
  name: string;
  tools: string[];
  description: string;
  created_at: string;
}

export interface CustomAgentCreateRequest {
  agent_id?: string | null;
  name: string;
  system_prompt: string;
  tools: ToolConfig[];
  metadata?: Record<string, unknown>;
}

export interface CustomAgentCreateResponse {
  agent_id: string;
  name: string;
  message: string;
}

// Workflow types
export interface WorkflowInfo {
  workflow_id: string;
  agents: string[];
  provider: string;
  model?: string | null;
  created_at: string;
}

export interface WorkflowCreateRequest {
  workflow_id?: string | null;
  agents: string[];
  provider?: string;
  model?: string | null;
  supervisor_prompt?: string | null;
}

export interface WorkflowCreateResponse {
  workflow_id: string;
  agents: string[];
  message: string;
}

export interface WorkflowInvokeRequest {
  message: string;
  session_id?: string | null;
}

export interface WorkflowInvokeResponse {
  workflow_id: string;
  response: string;
  agents_used: string[];
  session_id?: string | null;
}

// Health types
export interface HealthResponse {
  status: string;
  timestamp: string;
}

export interface StatusResponse {
  status: string;
  timestamp: string;
  providers: ProviderInfo[];
  active_sessions: number;
  cached_models: number;
  tracing_enabled: boolean;
}
