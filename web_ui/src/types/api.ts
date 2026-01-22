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
  event: 'start' | 'token' | 'tool_call' | 'tool_result' | 'done' | 'error' | 'agent_start' | 'agent_end' | 'approval_request';
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
  // Workflow-specific fields
  workflow_id?: string;
  agents?: string[];
  agent_name?: string;
  agent_id?: string;
  response?: string;
  message_count?: number;
  // HITL approval fields
  approval_id?: string;
  tool_args?: Record<string, unknown>;
  expires_at?: string;
  config?: {
    show_args?: boolean;
    timeout_seconds?: number;
    require_reason_on_reject?: boolean;
  };
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
  provider?: string;
  model?: string | null;
  temperature?: number;
}

export interface CustomAgentCreateRequest {
  agent_id?: string | null;
  name: string;
  system_prompt: string;
  tools: ToolConfig[];
  skills?: string[];
  schedule?: ScheduleConfig | null;
  metadata?: Record<string, unknown>;
  provider?: string;
  model?: string | null;
  temperature?: number;
}

export interface CustomAgentCreateResponse {
  agent_id: string;
  name: string;
  tools: string[];
  schedule_enabled: boolean;
  message: string;
}

// Starter Prompts types
export interface StarterPrompt {
  title: string;
  prompt: string;
  icon: string;
}

export interface StarterPromptCategory {
  category: string;
  icon: string;
  prompts: StarterPrompt[];
}

export interface StarterPromptsResponse {
  agent_id: string;
  agent_name: string;
  categories: StarterPromptCategory[];
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
  images?: string[];  // Base64 data URIs for images
  session_id?: string | null;
  // Memory options for unified conversation management
  enable_memory?: boolean;
  memory_trigger_count?: number | null;
  memory_keep_recent?: number | null;
}

export interface WorkflowInvokeResponse {
  workflow_id: string;
  response: string;
  agents: string[];
  message_count: number;
  session_id: string;
  memory_metadata?: MemoryMetadata | null;
}

// Direct agent invocation (no supervisor) for human-in-the-loop
export interface DirectInvokeRequest {
  message: string;
  images?: string[];  // Base64 data URIs for images
  session_id?: string | null;
  // Provider/model override - allows UI to override agent defaults
  provider?: string | null;
  model?: string | null;
  temperature?: number | null;
  // Memory options for unified conversation management
  enable_memory?: boolean;
  memory_trigger_count?: number | null;
  memory_keep_recent?: number | null;
  // MCP servers to enable for this request
  mcp_servers?: string[];
}

export interface DirectInvokeResponse {
  agent_id: string;
  session_id: string;
  response: string;
  message_count: number;
  memory_metadata?: MemoryMetadata | null;
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

// Tool configuration from SKILL.md frontmatter
export interface SkillToolConfigArg {
  name: string;
  type: string;
  description?: string;
  required: boolean;
  default?: unknown;
}

export interface SkillToolConfig {
  name: string;
  description: string;
  method: string;
  args: SkillToolConfigArg[];
  requires_skill_loaded?: boolean;
}

// Resource configuration from SKILL.md frontmatter
export interface SkillResourceConfig {
  name: string;
  description: string;
  file?: string | null;
  content?: string | null;
  dynamic?: boolean;
  method?: string | null;
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
  tool_configs?: SkillToolConfig[];
  resource_configs?: SkillResourceConfig[];
  has_custom_content?: boolean;
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
  change_summary?: string | null;
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

// Skill Versioning types
export interface SkillVersionInfo {
  version_number: number;
  semantic_version: string;
  change_summary: string | null;
  created_at: string;
  author: string | null;
  is_active: boolean;
}

export interface SkillVersionDetail extends SkillVersionInfo {
  name: string;
  description: string;
  category: string;
  core_content: string;
  resources: SkillResource[];
  scripts: SkillScript[];
}

export interface SkillUsageMetrics {
  total_loads: number;
  unique_sessions: number;
  last_loaded_at: string | null;
  loads_by_version: Record<number, number>;
}

export interface VersionedSkillInfo extends SkillInfo {
  active_version: number;
  version_count: number;
  versions: SkillVersionInfo[];
  metrics: SkillUsageMetrics | null;
}

export interface SkillVersionListResponse {
  skill_id: string;
  versions: SkillVersionInfo[];
  total: number;
  limit: number;
  offset: number;
}

export interface SkillDiffField {
  field: string;
  from_value: string | null;
  to_value: string | null;
}

export interface SkillDiffResponse {
  skill_id: string;
  from_version: number;
  to_version: number;
  changes: SkillDiffField[];
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
  status: 'available' | 'disabled' | 'unknown' | 'error';
  is_custom?: boolean;
  url?: string | null;
  tool_count?: number | null;
  tools?: MCPToolInfo[] | null;
}

export interface MCPServersResponse {
  servers: MCPServerInfo[];
}

export interface MCPServerStartResponse {
  id: string;
  status: 'available' | 'disabled' | 'unknown' | 'error';
  message: string;
  tools?: MCPToolInfo[] | null;
}

export interface MCPServerStopResponse {
  id: string;
  status: 'available' | 'disabled' | 'unknown';
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

// Capability types (Unified Tools and Skills)
export interface CapabilityParameter {
  name: string;
  type: string;
  description: string;
  default?: unknown;
  required: boolean;
}

export interface Capability {
  id: string;
  name: string;
  description: string;
  category: string;
  type: 'tool' | 'skill_bundle';
  tools_provided: string[];
  parameters: CapabilityParameter[];
}

export interface CapabilityListResponse {
  capabilities: Capability[];
  total: number;
}

// Knowledge Base / RAG types
export interface KBDocument {
  id: string;
  filename: string;
  content_type: 'pdf' | 'markdown' | 'text';
  chunk_count: number;
  size: number;
  collection: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface KBCollection {
  id: string;
  name: string;
  document_count: number;
  color?: string | null;
}

export interface KBSearchResult {
  document_id: string;
  chunk_id: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface KBStats {
  total_documents: number;
  total_chunks: number;
  total_collections: number;
  index_size: string;
  last_updated: string;
  available: boolean;
}

export interface KBDocumentListResponse {
  documents: KBDocument[];
  total: number;
}

export interface KBCollectionListResponse {
  collections: KBCollection[];
  total: number;
}

export interface KBSearchRequest {
  query: string;
  top_k?: number;
  min_score?: number;
  collection?: string | null;
}

export interface KBSearchResponse {
  query: string;
  results: KBSearchResult[];
  total: number;
}

export interface KBDocumentUploadRequest {
  content: string;
  filename: string;
  collection?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface KBFileUploadResponse {
  document: KBDocument;
  message: string;
}

export interface KBDeleteResponse {
  success: boolean;
  message: string;
}

export interface KBContextResponse {
  query: string;
  context: string;
  has_context: boolean;
}
