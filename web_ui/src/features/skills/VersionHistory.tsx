/**
 * Version History component for displaying and managing skill versions.
 * Shows a timeline of all versions with rollback capability.
 */

import { useEffect, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
  History,
  GitBranch,
  Check,
  RotateCcw,
  Loader2,
  AlertCircle,
  GitCompare,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useSkillStore } from '@/stores/skillStore';
import type { SkillVersionInfo } from '@/types/api';

interface VersionHistoryProps {
  skillId: string;
  isBuiltin?: boolean;
}

export function VersionHistory({ skillId, isBuiltin = false }: VersionHistoryProps) {
  const {
    versions,
    versionsTotal,
    isLoading,
    error,
    fetchVersions,
    activateVersion,
    fetchDiff,
    clearDiff,
    diffResult,
  } = useSkillStore();

  const [selectedVersion, setSelectedVersion] = useState<SkillVersionInfo | null>(null);
  const [showRollbackDialog, setShowRollbackDialog] = useState(false);
  const [isActivating, setIsActivating] = useState(false);
  const [showDiffDialog, setShowDiffDialog] = useState(false);

  useEffect(() => {
    if (skillId) {
      fetchVersions(skillId);
    }
  }, [skillId, fetchVersions]);

  const handleRollback = async () => {
    if (!selectedVersion) return;
    setIsActivating(true);
    try {
      await activateVersion(skillId, selectedVersion.version_number);
      setShowRollbackDialog(false);
      setSelectedVersion(null);
    } finally {
      setIsActivating(false);
    }
  };

  const handleCompare = async (version: SkillVersionInfo) => {
    // Find the active version
    const activeVersion = versions.find((v) => v.is_active);
    if (!activeVersion || activeVersion.version_number === version.version_number) return;

    const fromVersionNum = Math.min(version.version_number, activeVersion.version_number);
    const toVersionNum = Math.max(version.version_number, activeVersion.version_number);

    await fetchDiff(skillId, fromVersionNum, toVersionNum);
    setShowDiffDialog(true);
  };

  const formatDate = (dateStr: string) => {
    try {
      return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
    } catch {
      return dateStr;
    }
  };

  if (isBuiltin) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            <History className="h-12 w-12 mb-4 opacity-50" />
            <p className="text-lg font-medium">Built-in Skill</p>
            <p className="text-sm">Version history is not available for built-in skills.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading && versions.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-muted-foreground">Loading versions...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col items-center justify-center py-8 text-destructive">
            <AlertCircle className="h-12 w-12 mb-4" />
            <p className="text-lg font-medium">Error loading versions</p>
            <p className="text-sm">{error}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (versions.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            <History className="h-12 w-12 mb-4 opacity-50" />
            <p className="text-lg font-medium">No Version History</p>
            <p className="text-sm">
              Versioning requires Redis to be configured.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            Version History
            <Badge variant="outline" className="ml-2">
              {versionsTotal} version{versionsTotal !== 1 ? 's' : ''}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[400px] pr-4">
            <div className="space-y-4">
              {versions.map((version, index) => (
                <div
                  key={version.version_number}
                  className={`
                    relative pl-8 pb-4
                    ${index < versions.length - 1 ? 'border-l-2 border-muted ml-3' : 'ml-3'}
                  `}
                >
                  {/* Timeline dot */}
                  <div
                    className={`
                      absolute left-0 -translate-x-1/2 w-6 h-6 rounded-full
                      flex items-center justify-center
                      ${version.is_active
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted border-2 border-background'
                      }
                    `}
                  >
                    {version.is_active ? (
                      <Check className="h-3 w-3" />
                    ) : (
                      <span className="text-xs font-medium">{version.version_number}</span>
                    )}
                  </div>

                  {/* Version content */}
                  <div className="bg-card border rounded-lg p-4 ml-4">
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">
                            v{version.semantic_version}
                          </span>
                          {version.is_active && (
                            <Badge variant="default" className="text-xs">
                              Active
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {formatDate(version.created_at)}
                          {version.author && ` by ${version.author}`}
                        </p>
                        {version.change_summary && (
                          <p className="text-sm mt-2">{version.change_summary}</p>
                        )}
                      </div>

                      <div className="flex gap-2">
                        {!version.is_active && (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleCompare(version)}
                              title="Compare with active version"
                            >
                              <GitCompare className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setSelectedVersion(version);
                                setShowRollbackDialog(true);
                              }}
                              title="Rollback to this version"
                            >
                              <RotateCcw className="h-4 w-4 mr-1" />
                              Rollback
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Rollback Confirmation Dialog */}
      <Dialog open={showRollbackDialog} onOpenChange={setShowRollbackDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rollback to Previous Version</DialogTitle>
            <DialogDescription>
              Are you sure you want to rollback to version{' '}
              <strong>v{selectedVersion?.semantic_version}</strong>?
              This will set this version as the active version.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowRollbackDialog(false);
                setSelectedVersion(null);
              }}
              disabled={isActivating}
            >
              Cancel
            </Button>
            <Button onClick={handleRollback} disabled={isActivating}>
              {isActivating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Rolling back...
                </>
              ) : (
                <>
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Rollback
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Diff Dialog */}
      <Dialog open={showDiffDialog} onOpenChange={(open: boolean) => {
        setShowDiffDialog(open);
        if (!open) clearDiff();
      }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Version Comparison</DialogTitle>
            <DialogDescription>
              Changes between versions
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 max-h-[400px] overflow-auto">
            {diffResult?.changes.length === 0 ? (
              <p className="text-muted-foreground text-center py-4">
                No changes detected between these versions.
              </p>
            ) : (
              diffResult?.changes.map((change, index) => (
                <div key={index} className="border rounded-lg p-4">
                  <div className="font-medium capitalize mb-2">{change.field}</div>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <div className="text-muted-foreground mb-1">From:</div>
                      <pre className="bg-destructive/10 p-2 rounded text-xs whitespace-pre-wrap">
                        {change.from_value || '(empty)'}
                      </pre>
                    </div>
                    <div>
                      <div className="text-muted-foreground mb-1">To:</div>
                      <pre className="bg-green-500/10 p-2 rounded text-xs whitespace-pre-wrap">
                        {change.to_value || '(empty)'}
                      </pre>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
          <DialogFooter>
            <Button onClick={() => {
              setShowDiffDialog(false);
              clearDiff();
            }}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
