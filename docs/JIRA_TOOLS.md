# Jira Tools Reference

This document covers the Jira integration tools available in the LangChain Docker application.

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Jira instance URL
JIRA_URL=https://your-org.atlassian.net

# OAuth 2.0 access token (Bearer token)
JIRA_BEARER_TOKEN=your-oauth-access-token

# API version (optional, defaults to "2")
JIRA_API_VERSION=2
```

### Authentication

The integration uses **Bearer token authentication** with OAuth 2.0:

```
Authorization: Bearer <your-access-token>
```

**Required OAuth scopes:**
- `read:jira-work` - Read issues, projects, boards
- `read:jira-user` - Read user information
- `read:sprint:jira-software` - Read sprints (for agile features)

**Note:** OAuth tokens expire (typically 1 hour). If you see 401 errors, refresh your token.

## Available Tools

All tools are **read-only** - no create, update, or delete operations.

### Skill Loading Tools

| Tool | Description | Use When |
|------|-------------|----------|
| `load_jira_skill` | Load Jira skill with context and guidelines | First step before using other Jira tools |
| `jira_jql_reference` | Load JQL syntax reference documentation | Need help writing JQL queries |

### Issue Query Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `jira_search` | Search issues using JQL | `jql` (required), `max_results` (default: 50) |
| `jira_get_issue` | Get detailed issue information | `issue_key` (e.g., "PROJ-123") |

### Issue Detail Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `jira_get_comments` | Get user comments and discussions | `issue_key`, `max_results` (default: 50) |
| `jira_get_changelog` | Get field change history (status, assignee changes) | `issue_key` |
| `jira_get_worklogs` | Get time logged on issue | `issue_key` |

### Project & Agile Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `jira_list_projects` | List all accessible projects | - |
| `jira_get_boards` | List agile boards | `project_key` (optional), `board_type` (scrum/kanban) |
| `jira_get_sprints` | Get sprints for a board | `board_id`, `state` (active/closed/future) |
| `jira_get_sprint_issues` | Get issues in a sprint | `sprint_id` |

## Sample Questions

### Basic Issue Queries

| Question | Expected Tool(s) |
|----------|------------------|
| "What is PROJ-123 about?" | `jira_get_issue` |
| "Who is working on PROJ-123?" | `jira_get_issue` (returns assignee) |
| "What's the status of PROJ-123?" | `jira_get_issue` |
| "Show me all bugs assigned to me" | `jira_search` with JQL: `assignee = currentUser() AND type = Bug` |
| "Find open issues in project PROJ" | `jira_search` with JQL: `project = PROJ AND status != Done` |

### Comments & History

| Question | Expected Tool(s) |
|----------|------------------|
| "What was the last comment on PROJ-123?" | `jira_get_comments` |
| "Show me the discussion on PROJ-123" | `jira_get_comments` |
| "Who changed the status of PROJ-123?" | `jira_get_changelog` |
| "What changes were made to PROJ-123?" | `jira_get_changelog` |
| "How much time was logged on PROJ-123?" | `jira_get_worklogs` |

### Projects & Sprints

| Question | Expected Tool(s) |
|----------|------------------|
| "What projects do I have access to?" | `jira_list_projects` |
| "Show me the scrum boards" | `jira_get_boards` |
| "What's in the current sprint?" | `jira_get_boards` → `jira_get_sprints` → `jira_get_sprint_issues` |
| "List active sprints for board 123" | `jira_get_sprints` with `board_id=123, state=active` |

### JQL Help

| Question | Expected Tool(s) |
|----------|------------------|
| "How do I write a JQL query?" | `jira_jql_reference` |
| "What JQL functions are available?" | `jira_jql_reference` |

## API Endpoints Called

| Tool | Jira REST API Endpoint |
|------|------------------------|
| `jira_search` | `GET /rest/api/2/search?jql=...` |
| `jira_get_issue` | `GET /rest/api/2/issue/{key}` |
| `jira_get_comments` | `GET /rest/api/2/issue/{key}/comment` |
| `jira_get_changelog` | `GET /rest/api/2/issue/{key}?expand=changelog` |
| `jira_get_worklogs` | `GET /rest/api/2/issue/{key}/worklog` |
| `jira_list_projects` | `GET /rest/api/2/project` |
| `jira_get_boards` | `GET /rest/agile/1.0/board` |
| `jira_get_sprints` | `GET /rest/agile/1.0/board/{id}/sprint` |
| `jira_get_sprint_issues` | `GET /rest/agile/1.0/sprint/{id}/issue` |

## Common JQL Examples

```sql
-- Issues assigned to me
assignee = currentUser()

-- Open bugs in a project
project = PROJ AND type = Bug AND status != Done

-- Issues updated in last 7 days
updated >= -7d

-- High priority issues
priority in (High, Highest)

-- Issues in current sprint
sprint in openSprints()

-- Issues created this week
created >= startOfWeek()

-- Unassigned issues
assignee is EMPTY

-- Issues with specific label
labels = "backend"

-- Combined query
project = PROJ AND type = Bug AND priority = High AND status != Done ORDER BY created DESC
```

## Troubleshooting

### Authentication Errors

**401 Unauthorized:**
```
[Jira API] AUTH ERROR 401: Token expired or invalid. Please refresh your OAuth token.
```
**Solution:** Your OAuth token has expired. Generate a new access token.

**403 Forbidden:**
```
[Jira API] AUTH ERROR 403: Forbidden. Token may lack required scopes.
```
**Solution:** Ensure your OAuth app has the required scopes: `read:jira-work`, `read:jira-user`.

### Common Issues

| Issue | Solution |
|-------|----------|
| Empty responses | Check if you have access to the project/issue |
| "Issue does not exist" | Verify the issue key format (e.g., PROJ-123) |
| Agile endpoints failing | Ensure the project uses Scrum/Kanban boards |
| Slow responses | Reduce `max_results` parameter |

### Logging

API calls are logged with the `[Jira API]` prefix:

```
[Jira API] GET https://your-org.atlassian.net/rest/api/2/issue/PROJ-123 params={}
[Jira API] Response: 200
[Jira API] Success - response keys: ['key', 'fields', ...]
```

Error responses include detailed messages:
```
[Jira API] Response: 401
[Jira API] AUTH ERROR 401: Token expired or invalid. Please refresh your OAuth token.
```

## Progressive Disclosure Pattern

The Jira tools follow the progressive disclosure pattern:

```
Level 1: Metadata (always visible)
         └── "jira: Query Jira issues, sprints, projects" in system prompt

Level 2: load_jira_skill (on-demand)
         └── Returns configuration status + SKILL.md guidelines
         └── Unlocks gated tools (jira_search, jira_get_issue, etc.)

Level 3: jira_jql_reference (as needed)
         └── Returns detailed JQL syntax documentation
```

**Important:** The agent should call `load_jira_skill` before using other Jira tools to ensure proper context is loaded.
