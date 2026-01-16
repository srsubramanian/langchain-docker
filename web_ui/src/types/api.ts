// Chat types
export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  images?: string[];  // Base64 data URIs for uploaded images
  timestamp?: string;
  metadata?: Record<string, unknown>;
}

export interface ChatRequest {
  message: string;
  images?: string[];  // Base64 data URIs for images
  session_id?: string | null;
  provider?: string;
  model?: string | null;
  temperature?: number;
  stream?: boolean;
  max_tokens?: number | null;
  enable_memory?: boolean;
  mcp_servers?: string[] | null;
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
  event: 'start' | 'token' | 'tool_call' | 'tool_result' | 'done' | 'error';
  session_id?: string;
  model?: string;
  provider?: string;
  content?: string;
  message?: Message;
  conversation_length?: number;
  memory_metadata?: MemoryMetadata;
  mcp_tools_count?: number;
  // Tool call/result fields
  tool_name?: string;
  tool_id?: string;
  arguments?: string;
  result?: string;
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

// Schedule types
export interface ScheduleConfig {
  enabled: boolean;
  cron_expression: string;
  trigger_prompt: string;
  timezone?: string;
}

export interface ScheduleInfo {
  enabled: boolean;
  cron_expression: string;
  trigger_prompt: string;
  timezone: string;
  next_run?: string | null;
}

export interface CustomAgentInfo {
  id: string;
  name: string;
  tools: string[];
  skills: string[];
  description: string;
  schedule?: ScheduleInfo | null;
  created_at: string;
}

export interface CustomAgentCreateRequest {
  agent_id?: string | null;
  name: string;
  system_prompt: string;
  tools: ToolConfig[];
  skills?: string[];
  schedule?: ScheduleConfig | null;
  metadata?: Record<string, unknown>;
}

export interface CustomAgentCreateResponse {
  agent_id: string;
  name: string;
  tools: string[];
  schedule_enabled: boolean;
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

// Skills types (Progressive Disclosure Pattern)
export interface SkillMetadata {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  author?: string | null;
}

export interface SkillResource {
  name: string;
  description: string;
  content?: string | null;
}

export interface SkillScript {
  name: string;
  description: string;
  language: string;
  content?: string | null;
}

export interface SkillInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  author?: string | null;
  is_builtin: boolean;
  core_content?: string | null;
  resources: SkillResource[];
  scripts: SkillScript[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SkillListResponse {
  skills: SkillMetadata[];
  total: number;
}

export interface SkillCreateRequest {
  id?: string | null;
  name: string;
  description: string;
  category: string;
  version?: string;
  author?: string | null;
  core_content: string;
  resources?: SkillResource[];
  scripts?: SkillScript[];
}

export interface SkillUpdateRequest {
  name?: string | null;
  description?: string | null;
  category?: string | null;
  version?: string | null;
  author?: string | null;
  core_content?: string | null;
  resources?: SkillResource[] | null;
  scripts?: SkillScript[] | null;
}

export interface SkillCreateResponse {
  skill_id: string;
  name: string;
  message: string;
}

export interface SkillDeleteResponse {
  skill_id: string;
  deleted: boolean;
}

export interface SkillLoadResponse {
  skill_id: string;
  name: string;
  content: string;
}

// MCP Server types
export interface MCPToolInfo {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export interface MCPServerInfo {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  status: 'running' | 'stopped' | 'error';
  is_custom?: boolean;
  url?: string | null;
  tools?: MCPToolInfo[] | null;
}

export interface MCPServersResponse {
  servers: MCPServerInfo[];
}

export interface MCPServerStartResponse {
  id: string;
  status: 'running' | 'stopped' | 'error';
  message: string;
  tools?: MCPToolInfo[] | null;
}

export interface MCPServerStopResponse {
  id: string;
  status: 'stopped';
  message: string;
}

export interface MCPToolsResponse {
  server_id: string;
  tools: MCPToolInfo[];
}

export interface MCPToolCallRequest {
  tool_name: string;
  arguments: Record<string, unknown>;
}

export interface MCPToolCallResponse {
  server_id: string;
  tool_name: string;
  result: unknown;
  success: boolean;
  error?: string | null;
}

export interface MCPServerCreateRequest {
  url: string;
  name?: string;
  description?: string;
  timeout_seconds?: number;
}

export interface MCPServerCreateResponse {
  id: string;
  name: string;
  url: string;
  message: string;
}

export interface MCPServerDeleteResponse {
  id: string;
  deleted: boolean;
}
