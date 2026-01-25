# LangChain Docker - React Web UI

Modern React-based user interface for the LangChain Docker orchestration platform.

## Tech Stack

- **React 18** - UI framework
- **Vite** - Build tool and dev server
- **TypeScript** - Type safety
- **shadcn/ui** - Component library
- **Tailwind CSS** - Styling
- **Zustand** - State management
- **React Flow** - Multi-agent workflow visualization

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The UI will be available at http://localhost:3000

## Features

### Chat Interface
- Real-time SSE streaming with token-by-token display
- Provider selection (OpenAI, Anthropic, Google, Bedrock)
- Session persistence with Redis

### Multi-Agent Workflows (`/multiagent`)
- Visual React Flow diagrams showing agent coordination
- Supervisor-worker agent architecture
- Real-time workflow execution feedback

### Session Workspace
- **WorkspacePanel** - File manager integrated into chat
- Upload, download, delete files per session
- Storage usage tracking
- Files accessible to workspace-aware agent tools

### Agent Management (`/agents`)
- View and invoke built-in agents
- Create and manage custom agents
- Pre-configured agents like `chrome_trace_analyst`

### Custom Agent Builder (`/builder`)
- Drag-and-drop agent construction
- Tool selection with blue nodes
- Skill selection with purple nodes
- Live flow diagram preview

### Skills Management (`/skills`)
- Browse built-in and custom skills
- Edit skill content with versioning
- Progressive disclosure architecture

### Knowledge Base (`/knowledge-base`)
- Document upload (PDF, Markdown, Text)
- Vector search with OpenSearch
- GraphRAG with Neo4j

## Project Structure

```
src/
├── api/                    # API client functions
│   ├── chat.ts            # Chat streaming API
│   ├── sessions.ts        # Session CRUD
│   ├── agents.ts          # Agent management
│   ├── skills.ts          # Skills API
│   └── workspace.ts       # Workspace file operations
├── components/
│   ├── chat/              # Chat-related components
│   │   ├── WorkspacePanel.tsx  # Session file manager
│   │   ├── ApprovalCard.tsx    # HITL approval UI
│   │   └── ChatMessage.tsx     # Message rendering
│   └── ui/                # shadcn/ui components
├── features/
│   ├── chat/              # ChatPage - streaming chat
│   ├── multiagent/        # MultiAgentPage - React Flow
│   ├── agents/            # AgentsPage - agent management
│   ├── builder/           # BuilderPage - agent wizard
│   ├── skills/            # SkillsPage
│   └── knowledge-base/    # KnowledgeBasePage
├── stores/                # Zustand state stores
│   ├── sessionStore.ts    # Global session state
│   ├── settingsStore.ts   # User settings
│   ├── workspaceStore.ts  # Workspace panel state
│   └── mcpStore.ts        # MCP server state
└── App.tsx                # Routes and layout
```

## Key Components

### WorkspacePanel
Session-scoped file manager for uploading files that agents can access.

```tsx
import { WorkspacePanel } from '@/components/chat';

// In your page component
<WorkspacePanel />
```

Features:
- File upload with drag-and-drop
- File listing with size and date
- Download and delete actions
- Storage usage meter

### ApprovalCard
Inline UI for Human-in-the-Loop (HITL) tool approval.

```tsx
import { ApprovalCard } from '@/components/chat';

// Rendered automatically for pending approvals
<ApprovalCard approval={pendingApproval} onAction={handleApproval} />
```

## Environment Variables

The UI connects to the FastAPI backend. Configure via Vite env:

```bash
# .env.local
VITE_API_URL=http://localhost:8000
```

## Docker Build

The web UI is built and served via nginx in Docker:

```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY web_ui/package*.json ./
RUN npm ci
COPY web_ui/ .
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
```

## Development

### Adding a New Feature Page

1. Create feature directory in `src/features/`
2. Add page component with routing in `App.tsx`
3. Create API functions in `src/api/`
4. Add Zustand store if needed in `src/stores/`

### Adding Components

1. Use shadcn/ui CLI: `npx shadcn-ui@latest add <component>`
2. Custom components go in `src/components/`
3. Follow existing patterns for props and styling
