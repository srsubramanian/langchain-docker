"""Workspace Tool Provider for agent file operations.

Provides tools for agents to interact with session workspaces:
- List files
- Read files (with size limits)
- Write files
- Get workspace info
"""

import json
import logging
from typing import Any, Callable

from langchain_docker.api.services.tools.base import (
    ToolParameter,
    ToolProvider,
    ToolTemplate,
)

logger = logging.getLogger(__name__)


class WorkspaceToolProvider(ToolProvider):
    """Tool provider for workspace file operations.

    Unlike other providers, this one doesn't depend on a skill.
    It provides general-purpose file tools for any session.
    """

    def __init__(self, workspace_service: Any, session_id_getter: Callable[[], str]):
        """Initialize the workspace tool provider.

        Args:
            workspace_service: The WorkspaceService instance
            session_id_getter: Callable that returns the current session ID
        """
        self._workspace_service = workspace_service
        self._get_session_id = session_id_getter

    def get_skill_id(self) -> str:
        """Workspace tools don't require a skill."""
        return "workspace"

    def get_templates(self) -> list[ToolTemplate]:
        """Get workspace tool templates."""
        return [
            ToolTemplate(
                id="workspace_list",
                name="List Workspace Files",
                description="List all files in the current session's working folder",
                category="workspace",
                parameters=[],
                factory=self._create_list_tool,
            ),
            ToolTemplate(
                id="workspace_read",
                name="Read Workspace File",
                description="Read content from a file in the working folder. For large files, use max_bytes to limit output.",
                category="workspace",
                parameters=[
                    ToolParameter(
                        name="filename",
                        type="string",
                        description="Name of the file to read",
                        required=True,
                    ),
                    ToolParameter(
                        name="max_bytes",
                        type="integer",
                        description="Maximum bytes to read (default: 50000 for text, use smaller for JSON parsing)",
                        required=False,
                    ),
                ],
                factory=self._create_read_tool,
            ),
            ToolTemplate(
                id="workspace_write",
                name="Write Workspace File",
                description="Write content to a file in the working folder",
                category="workspace",
                parameters=[
                    ToolParameter(
                        name="filename",
                        type="string",
                        description="Name of the file to create/overwrite",
                        required=True,
                    ),
                    ToolParameter(
                        name="content",
                        type="string",
                        description="Content to write to the file",
                        required=True,
                    ),
                ],
                factory=self._create_write_tool,
            ),
            ToolTemplate(
                id="workspace_info",
                name="Get Workspace Info",
                description="Get information about the current session's working folder (path, size, limits)",
                category="workspace",
                parameters=[],
                factory=self._create_info_tool,
            ),
            ToolTemplate(
                id="workspace_delete",
                name="Delete Workspace File",
                description="Delete a file from the working folder",
                category="workspace",
                parameters=[
                    ToolParameter(
                        name="filename",
                        type="string",
                        description="Name of the file to delete",
                        required=True,
                    ),
                ],
                factory=self._create_delete_tool,
            ),
            ToolTemplate(
                id="workspace_extract_json",
                name="Extract from JSON File",
                description="Extract specific data from a large JSON file using a JSON path expression. Useful for large trace files.",
                category="workspace",
                parameters=[
                    ToolParameter(
                        name="filename",
                        type="string",
                        description="Name of the JSON file",
                        required=True,
                    ),
                    ToolParameter(
                        name="json_path",
                        type="string",
                        description="Dot-notation path to extract (e.g., 'categories.performance.score' or 'audits.largest-contentful-paint')",
                        required=True,
                    ),
                ],
                factory=self._create_extract_json_tool,
            ),
        ]

    def _create_list_tool(self) -> Callable[[], str]:
        """Create the workspace_list tool."""
        service = self._workspace_service
        get_session = self._get_session_id

        def workspace_list() -> str:
            """List all files in the session workspace."""
            session_id = get_session()
            if not session_id:
                return "Error: No active session"

            try:
                files = service.list_files(session_id)
                if not files:
                    return "Working folder is empty. Upload files to get started."

                result = "## Working Folder Contents\n\n"
                result += "| Filename | Size | Modified |\n"
                result += "|----------|------|----------|\n"
                for f in files:
                    result += f"| {f['filename']} | {f['size_human']} | {f.get('modified_at', 'N/A')} |\n"

                total_size = sum(f["size"] for f in files)
                result += f"\n**Total:** {len(files)} files, {service._human_readable_size(total_size)}"
                return result
            except Exception as e:
                return f"Error listing files: {str(e)}"

        return workspace_list

    def _create_read_tool(self) -> Callable[[str, int | None], str]:
        """Create the workspace_read tool."""
        service = self._workspace_service
        get_session = self._get_session_id

        def workspace_read(filename: str, max_bytes: int | None = 50000) -> str:
            """Read content from a file in the workspace."""
            session_id = get_session()
            if not session_id:
                return "Error: No active session"

            try:
                result = service.read_file(session_id, filename, max_bytes=max_bytes)
                content = result["content"]

                if result["truncated"]:
                    content += f"\n\n[Truncated at {result['truncated_at']} bytes. Total size: {result['size_human']}]"

                return content
            except FileNotFoundError:
                return f"Error: File not found: {filename}"
            except Exception as e:
                return f"Error reading file: {str(e)}"

        return workspace_read

    def _create_write_tool(self) -> Callable[[str, str], str]:
        """Create the workspace_write tool."""
        service = self._workspace_service
        get_session = self._get_session_id

        def workspace_write(filename: str, content: str) -> str:
            """Write content to a file in the workspace."""
            session_id = get_session()
            if not session_id:
                return "Error: No active session"

            try:
                result = service.write_file(session_id, filename, content)
                return f"Created file: {result['filename']} ({result['size_human']})"
            except ValueError as e:
                return f"Error: {str(e)}"
            except Exception as e:
                return f"Error writing file: {str(e)}"

        return workspace_write

    def _create_info_tool(self) -> Callable[[], str]:
        """Create the workspace_info tool."""
        service = self._workspace_service
        get_session = self._get_session_id

        def workspace_info() -> str:
            """Get workspace information."""
            session_id = get_session()
            if not session_id:
                return "Error: No active session"

            try:
                info = service.get_workspace_info(session_id)
                return f"""## Workspace Info

- **Session:** {info['session_id']}
- **Path:** {info['path']}
- **Files:** {info['file_count']}
- **Total Size:** {info['total_size_human']}
- **Max File Size:** {service._human_readable_size(info['max_file_size'])}
- **Max Workspace Size:** {service._human_readable_size(info['max_workspace_size'])}
- **TTL:** {info['ttl_hours']} hours (auto-cleanup)
"""
            except Exception as e:
                return f"Error getting workspace info: {str(e)}"

        return workspace_info

    def _create_delete_tool(self) -> Callable[[str], str]:
        """Create the workspace_delete tool."""
        service = self._workspace_service
        get_session = self._get_session_id

        def workspace_delete(filename: str) -> str:
            """Delete a file from the workspace."""
            session_id = get_session()
            if not session_id:
                return "Error: No active session"

            try:
                deleted = service.delete_file(session_id, filename)
                if deleted:
                    return f"Deleted: {filename}"
                else:
                    return f"File not found: {filename}"
            except Exception as e:
                return f"Error deleting file: {str(e)}"

        return workspace_delete

    def _create_extract_json_tool(self) -> Callable[[str, str], str]:
        """Create the workspace_extract_json tool."""
        service = self._workspace_service
        get_session = self._get_session_id

        def workspace_extract_json(filename: str, json_path: str) -> str:
            """Extract specific data from a JSON file using dot notation.

            This is useful for large JSON files (like Lighthouse reports or traces)
            where you only need specific values.

            Examples:
                - "categories.performance.score" -> 0.85
                - "audits.largest-contentful-paint.numericValue" -> 2500
            """
            session_id = get_session()
            if not session_id:
                return "Error: No active session"

            try:
                file_path = service.get_file_path(session_id, filename)
                if not file_path:
                    return f"Error: File not found: {filename}"

                # Read and parse JSON
                with open(file_path) as f:
                    data = json.load(f)

                # Navigate the path
                parts = json_path.replace("[", ".").replace("]", "").split(".")
                result = data

                for part in parts:
                    if not part:
                        continue
                    if isinstance(result, dict):
                        if part in result:
                            result = result[part]
                        else:
                            return f"Path not found: '{part}' in '{json_path}'"
                    elif isinstance(result, list):
                        try:
                            idx = int(part)
                            result = result[idx]
                        except (ValueError, IndexError):
                            return f"Invalid array index: '{part}' in '{json_path}'"
                    else:
                        return f"Cannot navigate into {type(result).__name__} at '{part}'"

                # Format result
                if isinstance(result, (dict, list)):
                    # Limit output size for large objects
                    formatted = json.dumps(result, indent=2)
                    if len(formatted) > 10000:
                        formatted = formatted[:10000] + "\n... [truncated]"
                    return formatted
                else:
                    return str(result)

            except json.JSONDecodeError as e:
                return f"Error: Invalid JSON file: {str(e)}"
            except Exception as e:
                return f"Error extracting from JSON: {str(e)}"

        return workspace_extract_json
