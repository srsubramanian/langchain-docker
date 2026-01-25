"""Workspace API endpoints for managing session working folders.

Provides file upload, download, list, and delete operations for session workspaces.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from langchain_docker.api.dependencies import get_workspace_service
from langchain_docker.api.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/sessions/{session_id}/workspace", tags=["workspace"])


# Response Models


class FileInfo(BaseModel):
    """Information about a file in the workspace."""

    filename: str
    path: str
    size: int
    size_human: str
    modified_at: str | None = None
    uploaded_at: str | None = None


class WorkspaceInfo(BaseModel):
    """Information about a session workspace."""

    session_id: str
    path: str
    file_count: int
    total_size: int
    total_size_human: str
    max_file_size: int
    max_workspace_size: int
    ttl_hours: int


class FileListResponse(BaseModel):
    """Response for listing files."""

    session_id: str
    files: list[FileInfo]
    total_count: int
    total_size: int
    total_size_human: str


class FileUploadResponse(BaseModel):
    """Response for file upload."""

    success: bool
    file: FileInfo


class FileDeleteResponse(BaseModel):
    """Response for file deletion."""

    success: bool
    filename: str
    message: str


class FileContentResponse(BaseModel):
    """Response for reading file content."""

    filename: str
    content: str
    size: int
    size_human: str
    truncated: bool
    truncated_at: int | None = None


class WriteFileRequest(BaseModel):
    """Request for writing a file."""

    filename: str = Field(..., description="Name of the file to create")
    content: str = Field(..., description="File content")


# Endpoints


@router.get("", response_model=WorkspaceInfo)
def get_workspace_info(
    session_id: str,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
):
    """Get workspace information and statistics.

    Args:
        session_id: The session identifier

    Returns:
        Workspace info including path, file count, size, limits
    """
    return workspace_service.get_workspace_info(session_id)


@router.get("/files", response_model=FileListResponse)
def list_files(
    session_id: str,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
):
    """List all files in the session workspace.

    Args:
        session_id: The session identifier

    Returns:
        List of files with metadata
    """
    files = workspace_service.list_files(session_id)
    total_size = sum(f["size"] for f in files)

    return FileListResponse(
        session_id=session_id,
        files=[FileInfo(**f) for f in files],
        total_count=len(files),
        total_size=total_size,
        total_size_human=workspace_service._human_readable_size(total_size),
    )


@router.post("/files", response_model=FileUploadResponse)
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
):
    """Upload a file to the session workspace.

    Args:
        session_id: The session identifier
        file: The file to upload

    Returns:
        Upload result with file info
    """
    try:
        content = await file.read()
        result = workspace_service.upload_file(
            session_id=session_id,
            filename=file.filename or "uploaded_file",
            content=content,
        )
        return FileUploadResponse(
            success=True,
            file=FileInfo(**result),
        )
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/files/write", response_model=FileUploadResponse)
def write_file(
    session_id: str,
    request: WriteFileRequest,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
):
    """Write/create a file in the workspace with text content.

    Args:
        session_id: The session identifier
        request: Filename and content

    Returns:
        File info
    """
    try:
        result = workspace_service.write_file(
            session_id=session_id,
            filename=request.filename,
            content=request.content,
        )
        return FileUploadResponse(
            success=True,
            file=FileInfo(**result),
        )
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Write failed: {str(e)}")


@router.get("/files/{filename}")
def download_file(
    session_id: str,
    filename: str,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
):
    """Download a file from the workspace.

    Args:
        session_id: The session identifier
        filename: Name of the file to download

    Returns:
        File content as download
    """
    file_path = workspace_service.get_file_path(session_id, filename)
    if not file_path:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/files/{filename}/content", response_model=FileContentResponse)
def read_file_content(
    session_id: str,
    filename: str,
    max_bytes: int | None = None,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
):
    """Read file content (with optional size limit for large files).

    Args:
        session_id: The session identifier
        filename: Name of the file to read
        max_bytes: Maximum bytes to return (for large files)

    Returns:
        File content and metadata
    """
    try:
        result = workspace_service.read_file(
            session_id=session_id,
            filename=filename,
            max_bytes=max_bytes,
        )
        return FileContentResponse(**result)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")


@router.delete("/files/{filename}", response_model=FileDeleteResponse)
def delete_file(
    session_id: str,
    filename: str,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
):
    """Delete a file from the workspace.

    Args:
        session_id: The session identifier
        filename: Name of the file to delete

    Returns:
        Deletion result
    """
    deleted = workspace_service.delete_file(session_id, filename)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    return FileDeleteResponse(
        success=True,
        filename=filename,
        message=f"File '{filename}' deleted successfully",
    )


@router.delete("", response_model=dict)
def delete_workspace(
    session_id: str,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
):
    """Delete the entire workspace for a session.

    Args:
        session_id: The session identifier

    Returns:
        Deletion result
    """
    deleted = workspace_service.delete_workspace(session_id)
    return {
        "success": deleted,
        "session_id": session_id,
        "message": "Workspace deleted" if deleted else "Workspace not found",
    }
