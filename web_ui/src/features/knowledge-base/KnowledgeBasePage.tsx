import { useEffect, useCallback, useRef } from 'react';
import { FileText, Layers, FolderOpen, Upload, Search, AlertCircle, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useKnowledgeBaseStore } from '@/stores/knowledgeBaseStore';
import { cn } from '@/lib/cn';

export function KnowledgeBasePage() {
  const {
    stats,
    recentDocuments,
    collections,
    searchResults,
    searchQuery,
    isLoading,
    isSearching,
    isUploading,
    error,
    fetchStats,
    fetchRecentDocuments,
    fetchCollections,
    uploadFile,
    deleteDocument,
    search,
    clearSearch,
    clearError,
  } = useKnowledgeBaseStore();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Load initial data
  useEffect(() => {
    fetchStats();
    fetchRecentDocuments();
    fetchCollections();
  }, [fetchStats, fetchRecentDocuments, fetchCollections]);

  // Handle file upload
  const handleFileUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    for (const file of Array.from(files)) {
      try {
        await uploadFile(file);
      } catch {
        // Error is handled in store
      }
    }
  }, [uploadFile]);

  // Handle drag and drop
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    handleFileUpload(e.dataTransfer.files);
  }, [handleFileUpload]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  // Handle search
  const handleSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    const query = searchInputRef.current?.value || '';
    if (query.trim()) {
      search(query);
    }
  }, [search]);

  // Handle document delete
  const handleDelete = useCallback(async (id: string, filename: string) => {
    if (window.confirm(`Delete "${filename}"?`)) {
      try {
        await deleteDocument(id);
      } catch {
        // Error is handled in store
      }
    }
  }, [deleteDocument]);

  // Format file size
  const formatSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  // Format relative time
  const formatRelativeTime = (dateStr: string): string => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  // Get file icon based on content type
  const getFileIcon = (contentType: string) => {
    switch (contentType) {
      case 'pdf':
        return '📄';
      case 'markdown':
        return '📝';
      default:
        return '📃';
    }
  };

  return (
    <div className="container py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Knowledge Base</h1>
          <p className="text-muted-foreground">
            Your personal RAG knowledge store
          </p>
        </div>
        <Button onClick={() => fileInputRef.current?.click()} disabled={isUploading}>
          <Upload className="h-4 w-4 mr-2" />
          {isUploading ? 'Uploading...' : 'Add Content'}
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.md,.txt"
          multiple
          onChange={(e) => handleFileUpload(e.target.files)}
        />
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>{error}</span>
            <Button variant="ghost" size="sm" onClick={clearError}>
              Dismiss
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Documents</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? '...' : stats?.total_documents ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Uploaded files
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Chunks</CardTitle>
            <Layers className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? '...' : stats?.total_chunks ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Indexed segments
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Collections</CardTitle>
            <FolderOpen className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? '...' : stats?.total_collections ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Organized groups
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search Bar */}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                ref={searchInputRef}
                placeholder="Search your knowledge base..."
                className="pl-10"
                defaultValue={searchQuery}
              />
            </div>
            <Button type="submit" disabled={isSearching}>
              {isSearching ? 'Searching...' : 'Search'}
            </Button>
            {searchQuery && (
              <Button type="button" variant="outline" onClick={clearSearch}>
                Clear
              </Button>
            )}
          </form>
        </CardContent>
      </Card>

      {/* Search Results */}
      {searchResults.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Search Results</CardTitle>
            <CardDescription>
              Found {searchResults.length} relevant chunks for "{searchQuery}"
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {searchResults.map((result, index) => (
              <div
                key={result.chunk_id}
                className="p-3 rounded-lg border bg-muted/50"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">
                    {result.metadata?.filename as string || 'Unknown'}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Score: {(result.score * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="text-sm text-muted-foreground line-clamp-3">
                  {result.content}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Documents */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Recent Documents</CardTitle>
            <CardDescription>
              Recently uploaded files
            </CardDescription>
          </CardHeader>
          <CardContent>
            {recentDocuments.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No documents yet. Upload your first file!
              </p>
            ) : (
              <div className="space-y-2">
                {recentDocuments.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 group"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-xl">{getFileIcon(doc.content_type)}</span>
                      <div className="min-w-0">
                        <p className="font-medium text-sm truncate">
                          {doc.filename}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {doc.chunk_count} chunks · {formatSize(doc.size)} · {formatRelativeTime(doc.created_at)}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8"
                      onClick={() => handleDelete(doc.id, doc.filename)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Collections */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Collections</CardTitle>
            <CardDescription>
              Organize your documents
            </CardDescription>
          </CardHeader>
          <CardContent>
            {collections.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No collections yet. Add a collection when uploading.
              </p>
            ) : (
              <div className="space-y-2">
                {collections.map((col) => (
                  <div
                    key={col.id}
                    className="flex items-center justify-between p-2 rounded-lg hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-3">
                      <FolderOpen className="h-5 w-5 text-muted-foreground" />
                      <span className="font-medium text-sm">{col.name}</span>
                    </div>
                    <span className="text-sm text-muted-foreground">
                      {col.document_count} docs
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Upload Zone */}
      <Card
        className={cn(
          'border-2 border-dashed transition-colors',
          isUploading && 'opacity-50 pointer-events-none'
        )}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        <CardContent className="flex flex-col items-center justify-center py-10">
          <Upload className="h-10 w-10 text-muted-foreground mb-4" />
          <p className="text-lg font-medium mb-1">
            {isUploading ? 'Uploading...' : 'Drop files here to upload'}
          </p>
          <p className="text-sm text-muted-foreground mb-4">
            or click to browse (PDF, MD, TXT)
          </p>
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
          >
            Browse Files
          </Button>
        </CardContent>
      </Card>

      {/* Availability Warning */}
      {stats && !stats.available && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Knowledge base is not available. Check OpenSearch connection.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
