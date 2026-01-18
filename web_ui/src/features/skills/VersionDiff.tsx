/**
 * VersionDiff component for side-by-side comparison of two skill versions.
 */

import { useEffect, useState } from 'react';
import { GitCompare, ChevronDown, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useSkillStore } from '@/stores/skillStore';

interface VersionDiffProps {
  skillId: string;
  isBuiltin?: boolean;
}

export function VersionDiff({ skillId, isBuiltin = false }: VersionDiffProps) {
  const {
    versions,
    versionsTotal,
    isLoading,
    error,
    fetchVersions,
    fetchDiff,
    diffResult,
    clearDiff,
  } = useSkillStore();

  const [fromVersion, setFromVersion] = useState<string>('');
  const [toVersion, setToVersion] = useState<string>('');
  const [isComparing, setIsComparing] = useState(false);

  useEffect(() => {
    if (skillId) {
      fetchVersions(skillId);
    }
    return () => {
      clearDiff();
    };
  }, [skillId, fetchVersions, clearDiff]);

  // Set initial version selections when versions load
  useEffect(() => {
    if (versions.length >= 2) {
      const activeVersion = versions.find((v) => v.is_active);
      const previousVersion = versions.find((v) => !v.is_active);

      if (previousVersion) {
        setFromVersion(previousVersion.version_number.toString());
      }
      if (activeVersion) {
        setToVersion(activeVersion.version_number.toString());
      }
    }
  }, [versions]);

  const handleCompare = async () => {
    if (!fromVersion || !toVersion) return;
    setIsComparing(true);
    try {
      await fetchDiff(skillId, parseInt(fromVersion), parseInt(toVersion));
    } finally {
      setIsComparing(false);
    }
  };

  if (isBuiltin) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            <GitCompare className="h-12 w-12 mb-4 opacity-50" />
            <p className="text-lg font-medium">Built-in Skill</p>
            <p className="text-sm">Version comparison is not available for built-in skills.</p>
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

  if (versions.length < 2) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            <GitCompare className="h-12 w-12 mb-4 opacity-50" />
            <p className="text-lg font-medium">Not Enough Versions</p>
            <p className="text-sm">
              At least 2 versions are needed for comparison.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GitCompare className="h-5 w-5" />
          Compare Versions
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Version selectors */}
        <div className="flex items-end gap-4">
          <div className="flex-1 space-y-2">
            <label className="text-sm font-medium">From Version</label>
            <Select value={fromVersion} onValueChange={setFromVersion}>
              <SelectTrigger>
                <SelectValue placeholder="Select version" />
              </SelectTrigger>
              <SelectContent>
                {versions.map((v) => (
                  <SelectItem
                    key={v.version_number}
                    value={v.version_number.toString()}
                    disabled={v.version_number.toString() === toVersion}
                  >
                    <span className="flex items-center gap-2">
                      v{v.semantic_version}
                      {v.is_active && (
                        <Badge variant="secondary" className="text-xs">Active</Badge>
                      )}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <ChevronDown className="h-5 w-5 rotate-[-90deg] text-muted-foreground" />

          <div className="flex-1 space-y-2">
            <label className="text-sm font-medium">To Version</label>
            <Select value={toVersion} onValueChange={setToVersion}>
              <SelectTrigger>
                <SelectValue placeholder="Select version" />
              </SelectTrigger>
              <SelectContent>
                {versions.map((v) => (
                  <SelectItem
                    key={v.version_number}
                    value={v.version_number.toString()}
                    disabled={v.version_number.toString() === fromVersion}
                  >
                    <span className="flex items-center gap-2">
                      v{v.semantic_version}
                      {v.is_active && (
                        <Badge variant="secondary" className="text-xs">Active</Badge>
                      )}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Button
            onClick={handleCompare}
            disabled={!fromVersion || !toVersion || isComparing}
          >
            {isComparing ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Comparing...
              </>
            ) : (
              <>
                <GitCompare className="h-4 w-4 mr-2" />
                Compare
              </>
            )}
          </Button>
        </div>

        {/* Diff results */}
        {diffResult && (
          <ScrollArea className="h-[400px] pr-4">
            {diffResult.changes.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <p className="text-lg font-medium">No Changes</p>
                <p className="text-sm">These versions are identical.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {diffResult.changes.map((change, index) => (
                  <div key={index} className="border rounded-lg overflow-hidden">
                    <div className="bg-muted px-4 py-2 font-medium capitalize border-b">
                      {change.field.replace(/_/g, ' ')}
                    </div>
                    <div className="grid grid-cols-2 divide-x">
                      <div className="p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant="outline" className="bg-destructive/10 text-destructive border-destructive/20">
                            v{versions.find((v) => v.version_number === diffResult.from_version)?.semantic_version}
                          </Badge>
                          <span className="text-xs text-muted-foreground">From</span>
                        </div>
                        <pre className="text-sm whitespace-pre-wrap font-mono bg-muted/50 p-2 rounded">
                          {change.from_value || '(empty)'}
                        </pre>
                      </div>
                      <div className="p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant="outline" className="bg-green-500/10 text-green-600 border-green-500/20">
                            v{versions.find((v) => v.version_number === diffResult.to_version)?.semantic_version}
                          </Badge>
                          <span className="text-xs text-muted-foreground">To</span>
                        </div>
                        <pre className="text-sm whitespace-pre-wrap font-mono bg-muted/50 p-2 rounded">
                          {change.to_value || '(empty)'}
                        </pre>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        )}

        {!diffResult && !isComparing && (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground border-2 border-dashed rounded-lg">
            <GitCompare className="h-12 w-12 mb-4 opacity-50" />
            <p className="text-lg font-medium">Select Versions to Compare</p>
            <p className="text-sm">Choose two versions and click Compare to see the differences.</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
