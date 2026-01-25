"""Workspace Service for managing session working folders.

Provides a "Working Folder" concept similar to Claude Cowork where each session
gets a dedicated workspace for file uploads, generated outputs, and temporary data.
"""

import json
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Service for managing session workspaces.

    Each session gets a dedicated folder where:
    - Users can upload files (traces, data files, etc.)
    - Agents can read/write files
    - Files are automatically cleaned up after TTL
    """

    def __init__(
        self,
        base_path: str | None = None,
        ttl_hours: int = 24,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        max_workspace_size: int = 500 * 1024 * 1024,  # 500MB
    ):
        """Initialize the workspace service.

        Args:
            base_path: Base directory for workspaces. Defaults to /tmp/workspaces
            ttl_hours: Hours before workspace is cleaned up
            max_file_size: Maximum single file size in bytes
            max_workspace_size: Maximum total workspace size in bytes
        """
        self.base_path = Path(base_path or os.getenv("WORKSPACE_PATH", "/tmp/workspaces"))
        self.ttl_hours = int(os.getenv("WORKSPACE_TTL_HOURS", str(ttl_hours)))
        self.max_file_size = max_file_size
        self.max_workspace_size = max_workspace_size

        # Ensure base path exists
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"WorkspaceService initialized with base_path={self.base_path}")

    def _secure_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal attacks."""
        # Remove any path components
        filename = os.path.basename(filename)
        # Replace potentially dangerous characters
        filename = filename.replace("..", "_").replace("/", "_").replace("\\", "_")
        # Ensure not empty
        if not filename:
            filename = "unnamed_file"
        return filename

    def get_workspace_path(self, session_id: str) -> Path:
        """Get or create the workspace folder for a session.

        Args:
            session_id: The session identifier

        Returns:
            Path to the workspace folder
        """
        # Sanitize session_id
        safe_session_id = self._secure_filename(session_id)
        workspace = self.base_path / safe_session_id
        workspace.mkdir(parents=True, exist_ok=True)

        # Update access time for TTL tracking
        metadata_file = workspace / ".workspace_metadata.json"
        metadata = {
            "session_id": session_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_accessed": datetime.utcnow().isoformat(),
        }
        if metadata_file.exists():
            try:
                existing = json.loads(metadata_file.read_text())
                metadata["created_at"] = existing.get("created_at", metadata["created_at"])
            except Exception:
                pass
        metadata_file.write_text(json.dumps(metadata, indent=2))

        return workspace

    def get_workspace_info(self, session_id: str) -> dict[str, Any]:
        """Get workspace information and statistics.

        Args:
            session_id: The session identifier

        Returns:
            Dict with workspace path, file count, total size, etc.
        """
        workspace = self.get_workspace_path(session_id)
        files = self.list_files(session_id)
        total_size = sum(f["size"] for f in files)

        return {
            "session_id": session_id,
            "path": str(workspace),
            "file_count": len(files),
            "total_size": total_size,
            "total_size_human": self._human_readable_size(total_size),
            "max_file_size": self.max_file_size,
            "max_workspace_size": self.max_workspace_size,
            "ttl_hours": self.ttl_hours,
        }

    def _human_readable_size(self, size: int) -> str:
        """Convert bytes to human readable string."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def upload_file(
        self,
        session_id: str,
        filename: str,
        content: bytes,
    ) -> dict[str, Any]:
        """Upload a file to the session workspace.

        Args:
            session_id: The session identifier
            filename: Original filename
            content: File content as bytes

        Returns:
            Dict with file info (path, size, etc.)

        Raises:
            ValueError: If file too large or workspace quota exceeded
        """
        # Check file size
        if len(content) > self.max_file_size:
            raise ValueError(
                f"File size ({self._human_readable_size(len(content))}) exceeds "
                f"maximum ({self._human_readable_size(self.max_file_size)})"
            )

        workspace = self.get_workspace_path(session_id)

        # Check workspace quota
        current_size = sum(f.stat().st_size for f in workspace.iterdir() if f.is_file() and not f.name.startswith("."))
        if current_size + len(content) > self.max_workspace_size:
            raise ValueError(
                f"Workspace quota exceeded. Current: {self._human_readable_size(current_size)}, "
                f"Max: {self._human_readable_size(self.max_workspace_size)}"
            )

        # Save file
        safe_filename = self._secure_filename(filename)
        file_path = workspace / safe_filename

        # Handle duplicate names
        if file_path.exists():
            base, ext = os.path.splitext(safe_filename)
            counter = 1
            while file_path.exists():
                safe_filename = f"{base}_{counter}{ext}"
                file_path = workspace / safe_filename
                counter += 1

        file_path.write_bytes(content)

        logger.info(f"Uploaded file {safe_filename} ({len(content)} bytes) to workspace {session_id}")

        return {
            "filename": safe_filename,
            "path": str(file_path),
            "size": len(content),
            "size_human": self._human_readable_size(len(content)),
            "uploaded_at": datetime.utcnow().isoformat(),
        }

    def list_files(self, session_id: str) -> list[dict[str, Any]]:
        """List all files in the session workspace.

        Args:
            session_id: The session identifier

        Returns:
            List of file info dicts
        """
        workspace = self.get_workspace_path(session_id)
        files = []

        for f in sorted(workspace.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                stat = f.stat()
                files.append({
                    "filename": f.name,
                    "path": str(f),
                    "size": stat.st_size,
                    "size_human": self._human_readable_size(stat.st_size),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        return files

    def get_file_path(self, session_id: str, filename: str) -> Path | None:
        """Get the full path to a file in the workspace.

        Args:
            session_id: The session identifier
            filename: The filename

        Returns:
            Path to the file, or None if not found
        """
        workspace = self.get_workspace_path(session_id)
        safe_filename = self._secure_filename(filename)
        file_path = workspace / safe_filename

        if file_path.exists() and file_path.is_file():
            return file_path
        return None

    def read_file(
        self,
        session_id: str,
        filename: str,
        max_bytes: int | None = None,
        encoding: str = "utf-8",
    ) -> dict[str, Any]:
        """Read a file from the workspace.

        Args:
            session_id: The session identifier
            filename: The filename
            max_bytes: Maximum bytes to read (for large files)
            encoding: Text encoding (use None for binary)

        Returns:
            Dict with file content and metadata

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        file_path = self.get_file_path(session_id, filename)
        if not file_path:
            raise FileNotFoundError(f"File not found: {filename}")

        stat = file_path.stat()
        truncated = False

        if max_bytes and stat.st_size > max_bytes:
            content_bytes = file_path.read_bytes()[:max_bytes]
            truncated = True
        else:
            content_bytes = file_path.read_bytes()

        # Try to decode as text
        try:
            if encoding:
                content = content_bytes.decode(encoding)
            else:
                content = content_bytes
        except UnicodeDecodeError:
            # Binary file - return base64 or indicate binary
            content = f"[Binary file: {stat.st_size} bytes]"

        return {
            "filename": filename,
            "content": content,
            "size": stat.st_size,
            "size_human": self._human_readable_size(stat.st_size),
            "truncated": truncated,
            "truncated_at": max_bytes if truncated else None,
        }

    def write_file(
        self,
        session_id: str,
        filename: str,
        content: str | bytes,
        encoding: str = "utf-8",
    ) -> dict[str, Any]:
        """Write a file to the workspace.

        Args:
            session_id: The session identifier
            filename: The filename
            content: File content (string or bytes)
            encoding: Text encoding for string content

        Returns:
            Dict with file info
        """
        if isinstance(content, str):
            content_bytes = content.encode(encoding)
        else:
            content_bytes = content

        return self.upload_file(session_id, filename, content_bytes)

    def delete_file(self, session_id: str, filename: str) -> bool:
        """Delete a file from the workspace.

        Args:
            session_id: The session identifier
            filename: The filename

        Returns:
            True if deleted, False if not found
        """
        file_path = self.get_file_path(session_id, filename)
        if file_path:
            file_path.unlink()
            logger.info(f"Deleted file {filename} from workspace {session_id}")
            return True
        return False

    def delete_workspace(self, session_id: str) -> bool:
        """Delete an entire workspace.

        Args:
            session_id: The session identifier

        Returns:
            True if deleted
        """
        safe_session_id = self._secure_filename(session_id)
        workspace = self.base_path / safe_session_id

        if workspace.exists():
            shutil.rmtree(workspace)
            logger.info(f"Deleted workspace {session_id}")
            return True
        return False

    def cleanup_expired_workspaces(self) -> int:
        """Clean up workspaces that have exceeded TTL.

        Returns:
            Number of workspaces cleaned up
        """
        cleaned = 0
        now = time.time()
        ttl_seconds = self.ttl_hours * 3600

        for workspace in self.base_path.iterdir():
            if not workspace.is_dir():
                continue

            metadata_file = workspace / ".workspace_metadata.json"
            should_delete = False

            if metadata_file.exists():
                try:
                    metadata = json.loads(metadata_file.read_text())
                    last_accessed = datetime.fromisoformat(metadata["last_accessed"])
                    age_seconds = now - last_accessed.timestamp()
                    if age_seconds > ttl_seconds:
                        should_delete = True
                except Exception:
                    # If metadata is corrupted, check folder mtime
                    if now - workspace.stat().st_mtime > ttl_seconds:
                        should_delete = True
            else:
                # No metadata, check folder mtime
                if now - workspace.stat().st_mtime > ttl_seconds:
                    should_delete = True

            if should_delete:
                try:
                    shutil.rmtree(workspace)
                    logger.info(f"Cleaned up expired workspace: {workspace.name}")
                    cleaned += 1
                except Exception as e:
                    logger.error(f"Failed to clean up workspace {workspace.name}: {e}")

        return cleaned

    def run_script(
        self,
        session_id: str,
        script: str,
        args: list[str] | None = None,
        timeout: int = 60,
    ) -> dict[str, Any]:
        """Run a script in the workspace context.

        Args:
            session_id: The session identifier
            script: Script name or command
            args: Script arguments
            timeout: Execution timeout in seconds

        Returns:
            Dict with stdout, stderr, return code
        """
        import subprocess

        workspace = self.get_workspace_path(session_id)

        cmd = [script] + (args or [])

        try:
            result = subprocess.run(
                cmd,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "return_code": -1,
                "stdout": "",
                "stderr": f"Script timed out after {timeout} seconds",
            }
        except Exception as e:
            return {
                "success": False,
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
            }
