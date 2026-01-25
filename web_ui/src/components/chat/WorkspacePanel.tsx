import { useCallback, useEffect, useRef } from 'react';
import {
  FolderOpen,
  Upload,
  File,
  FileJson,
  FileText,
  FileImage,
  Trash2,
  Download,
  X,
  RefreshCw,
  HardDrive,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useWorkspaceStore } from '@/stores/workspaceStore';
import { useSessionStore } from '@/stores/sessionStore';
import { cn } from '@/lib/cn';

// Get file icon based on extension
function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'json':
      return <FileJson className="h-4 w-4 text-yellow-500" />;
    case 'md':
    case 'txt':
    case 'log':
      return <FileText className="h-4 w-4 text-blue-500" />;
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'gif':
    case 'webp':
      return <FileImage className="h-4 w-4 text-purple-500" />;
    default:
      return <File className="h-4 w-4 text-gray-500" />;
  }
}

export function WorkspacePanel() {
  const { sessionId } = useSessionStore();
  const {
    files,
    info,
    isLoading,
    isUploading,
    error,
    isOpen,
    setOpen,
    fetchFiles,
    fetchInfo,
    uploadFile,
    deleteFile,
    downloadFile,
  } = useWorkspaceStore();

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch files when panel opens or session changes
  useEffect(() => {
    if (isOpen && sessionId) {
      fetchFiles(sessionId);
      fetchInfo(sessionId);
    }
  }, [isOpen, sessionId, fetchFiles, fetchInfo]);

  const handleUploadClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file && sessionId) {
        await uploadFile(sessionId, file);
        // Reset input so the same file can be uploaded again
        event.target.value = '';
      }
    },
    [sessionId, uploadFile]
  );

  const handleDelete = useCallback(
    async (filename: string) => {
      if (sessionId && confirm(`Delete "${filename}"?`)) {
        await deleteFile(sessionId, filename);
      }
    },
    [sessionId, deleteFile]
  );

  const handleDownload = useCallback(
    async (filename: string) => {
      if (sessionId) {
        await downloadFile(sessionId, filename);
      }
    },
    [sessionId, downloadFile]
  );

  const handleRefresh = useCallback(() => {
    if (sessionId) {
      fetchFiles(sessionId);
      fetchInfo(sessionId);
    }
  }, [sessionId, fetchFiles, fetchInfo]);

  // When closed, render nothing - the toggle button is controlled by the parent page
  if (!isOpen) {
    return null;
  }

  return (
    <div className="w-64 border-l bg-background flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FolderOpen className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium text-sm">Working Folder</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleRefresh}
            disabled={isLoading}
            title="Refresh"
          >
            <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setOpen(false)}
            title="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Storage Info */}
      {info && (
        <div className="px-3 py-2 border-b bg-muted/30">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <HardDrive className="h-3 w-3" />
            <span>
              {info.total_size_human} / {(info.max_workspace_size / 1024 / 1024).toFixed(0)} MB
            </span>
          </div>
        </div>
      )}

      {/* Upload Button */}
      <div className="p-3 border-b">
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={handleFileChange}
        />
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={handleUploadClick}
          disabled={isUploading || !sessionId}
        >
          {isUploading ? (
            <>
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              Uploading...
            </>
          ) : (
            <>
              <Upload className="h-4 w-4 mr-2" />
              Upload File
            </>
          )}
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="px-3 py-2 text-xs text-red-500 bg-red-50 dark:bg-red-900/20">
          {error}
        </div>
      )}

      {/* File List */}
      <ScrollArea className="flex-1">
        <div className="p-2">
          {!sessionId ? (
            <p className="text-xs text-muted-foreground text-center py-4">
              Start a chat to enable the working folder
            </p>
          ) : isLoading && files.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">
              Loading...
            </p>
          ) : files.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">
              No files yet. Upload files to get started.
            </p>
          ) : (
            <div className="space-y-1">
              {files.map((file) => (
                <div
                  key={file.filename}
                  className="group flex items-center gap-2 p-2 rounded-md hover:bg-muted/50 transition-colors"
                >
                  {getFileIcon(file.filename)}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate" title={file.filename}>
                      {file.filename}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {file.size_human}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => handleDownload(file.filename)}
                      title="Download"
                    >
                      <Download className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      onClick={() => handleDelete(file.filename)}
                      title="Delete"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Footer */}
      {files.length > 0 && (
        <div className="px-3 py-2 border-t text-xs text-muted-foreground">
          {files.length} file{files.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}
