/**
 * SkillMetricsPanel component for displaying skill usage metrics.
 */

import { useEffect } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
  BarChart3,
  Activity,
  Users,
  Clock,
  TrendingUp,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { useSkillStore } from '@/stores/skillStore';

interface SkillMetricsPanelProps {
  skillId: string;
  isBuiltin?: boolean;
}

export function SkillMetricsPanel({ skillId, isBuiltin = false }: SkillMetricsPanelProps) {
  const { metrics, isLoading, fetchMetrics, versions } = useSkillStore();

  useEffect(() => {
    if (skillId) {
      fetchMetrics(skillId);
    }
  }, [skillId, fetchMetrics]);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    try {
      return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
    } catch {
      return dateStr;
    }
  };

  // Calculate max loads for progress bar scaling
  const maxLoads = metrics?.loads_by_version
    ? Math.max(...Object.values(metrics.loads_by_version), 1)
    : 1;

  if (isBuiltin) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            <BarChart3 className="h-12 w-12 mb-4 opacity-50" />
            <p className="text-lg font-medium">Built-in Skill</p>
            <p className="text-sm">
              Usage metrics are tracked for built-in skills when Redis is configured.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isLoading && !metrics) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-muted-foreground">Loading metrics...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!metrics || (metrics.total_loads === 0 && metrics.unique_sessions === 0)) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            <BarChart3 className="h-12 w-12 mb-4 opacity-50" />
            <p className="text-lg font-medium">No Usage Data</p>
            <p className="text-sm">
              Metrics will appear here once this skill is loaded by agents.
            </p>
            <p className="text-xs mt-2">
              Note: Metrics tracking requires Redis to be configured.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Loads</p>
                <h3 className="text-2xl font-bold">{metrics.total_loads}</h3>
              </div>
              <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                <Activity className="h-6 w-6 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Unique Sessions</p>
                <h3 className="text-2xl font-bold">{metrics.unique_sessions}</h3>
              </div>
              <div className="h-12 w-12 rounded-full bg-blue-500/10 flex items-center justify-center">
                <Users className="h-6 w-6 text-blue-500" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Last Used</p>
                <h3 className="text-lg font-bold">{formatDate(metrics.last_loaded_at)}</h3>
              </div>
              <div className="h-12 w-12 rounded-full bg-green-500/10 flex items-center justify-center">
                <Clock className="h-6 w-6 text-green-500" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Loads by Version */}
      {Object.keys(metrics.loads_by_version).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Loads by Version
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {Object.entries(metrics.loads_by_version)
                .sort(([a], [b]) => parseInt(b) - parseInt(a)) // Sort by version descending
                .map(([versionNum, loadCount]) => {
                  const version = versions.find((v) => v.version_number === parseInt(versionNum));
                  const percentage = (loadCount / maxLoads) * 100;

                  return (
                    <div key={versionNum} className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">
                            v{version?.semantic_version || versionNum}
                          </span>
                          {version?.is_active && (
                            <Badge variant="secondary" className="text-xs">Active</Badge>
                          )}
                        </div>
                        <span className="text-muted-foreground">
                          {loadCount} load{loadCount !== 1 ? 's' : ''}
                        </span>
                      </div>
                      <Progress value={percentage} className="h-2" />
                    </div>
                  );
                })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Info Card */}
      <Card className="bg-muted/50">
        <CardContent className="pt-6">
          <div className="flex items-start gap-4">
            <AlertCircle className="h-5 w-5 text-muted-foreground mt-0.5" />
            <div className="space-y-1">
              <p className="text-sm font-medium">About Usage Metrics</p>
              <p className="text-sm text-muted-foreground">
                Metrics are tracked when agents load this skill using the <code>load_skill</code> tool.
                Unique sessions are counted within a 7-day rolling window.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
