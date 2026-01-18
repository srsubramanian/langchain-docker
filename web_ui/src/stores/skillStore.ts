/**
 * Zustand store for skill management with versioning support.
 */

import { create } from 'zustand';
import type {
  SkillInfo,
  SkillMetadata,
  SkillCreateRequest,
  SkillUpdateRequest,
  SkillVersionInfo,
  SkillVersionDetail,
  SkillUsageMetrics,
  SkillDiffResponse,
  VersionedSkillInfo,
} from '@/types/api';
import { skillsApi } from '@/api/skills';

interface SkillState {
  // Basic skill state
  skills: SkillMetadata[];
  selectedSkill: VersionedSkillInfo | null;
  isLoading: boolean;
  error: string | null;

  // Version history state
  versions: SkillVersionInfo[];
  versionsTotal: number;
  selectedVersion: SkillVersionDetail | null;
  diffResult: SkillDiffResponse | null;

  // Metrics state
  metrics: SkillUsageMetrics | null;

  // Actions - Basic CRUD
  fetchSkills: () => Promise<void>;
  fetchSkill: (skillId: string) => Promise<void>;
  createSkill: (request: SkillCreateRequest) => Promise<string>;
  updateSkill: (skillId: string, request: SkillUpdateRequest) => Promise<void>;
  deleteSkill: (skillId: string) => Promise<void>;

  // Actions - Versioning
  fetchVersions: (skillId: string, limit?: number, offset?: number) => Promise<void>;
  fetchVersion: (skillId: string, versionNumber: number) => Promise<void>;
  activateVersion: (skillId: string, versionNumber: number) => Promise<void>;
  fetchDiff: (skillId: string, fromVersion: number, toVersion: number) => Promise<void>;
  clearDiff: () => void;

  // Actions - Metrics
  fetchMetrics: (skillId: string) => Promise<void>;

  // Utility actions
  clearSelection: () => void;
  setError: (error: string | null) => void;
}

export const useSkillStore = create<SkillState>()((set, get) => ({
  // Initial state
  skills: [],
  selectedSkill: null,
  isLoading: false,
  error: null,
  versions: [],
  versionsTotal: 0,
  selectedVersion: null,
  diffResult: null,
  metrics: null,

  // Basic CRUD actions
  fetchSkills: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await skillsApi.list();
      set({ skills: response.skills, isLoading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to fetch skills',
        isLoading: false,
      });
    }
  },

  fetchSkill: async (skillId: string) => {
    set({ isLoading: true, error: null });
    try {
      // Use the versioned endpoint to get full version info
      const skill = await skillsApi.getVersioned(skillId);
      set({
        selectedSkill: skill,
        versions: skill.versions || [],
        versionsTotal: skill.version_count || 1,
        metrics: skill.metrics,
        isLoading: false,
      });
    } catch {
      // Fallback to basic get if versioned endpoint fails
      try {
        const basicSkill = await skillsApi.get(skillId);
        set({
          selectedSkill: {
            ...basicSkill,
            active_version: 1,
            version_count: 1,
            versions: [],
            metrics: null,
          } as VersionedSkillInfo,
          isLoading: false,
        });
      } catch (err) {
        set({
          error: err instanceof Error ? err.message : 'Failed to fetch skill',
          isLoading: false,
        });
      }
    }
  },

  createSkill: async (request: SkillCreateRequest) => {
    set({ isLoading: true, error: null });
    try {
      const response = await skillsApi.create(request);
      // Refresh skills list
      await get().fetchSkills();
      set({ isLoading: false });
      return response.skill_id;
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to create skill',
        isLoading: false,
      });
      throw err;
    }
  },

  updateSkill: async (skillId: string, request: SkillUpdateRequest) => {
    set({ isLoading: true, error: null });
    try {
      await skillsApi.update(skillId, request);
      // Refresh both skills list and selected skill
      await Promise.all([
        get().fetchSkills(),
        get().fetchSkill(skillId),
      ]);
      set({ isLoading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to update skill',
        isLoading: false,
      });
      throw err;
    }
  },

  deleteSkill: async (skillId: string) => {
    set({ isLoading: true, error: null });
    try {
      await skillsApi.delete(skillId);
      // Refresh skills list and clear selection
      await get().fetchSkills();
      set({ selectedSkill: null, isLoading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to delete skill',
        isLoading: false,
      });
      throw err;
    }
  },

  // Versioning actions
  fetchVersions: async (skillId: string, limit = 20, offset = 0) => {
    set({ isLoading: true, error: null });
    try {
      const response = await skillsApi.listVersions(skillId, limit, offset);
      set({
        versions: response.versions,
        versionsTotal: response.total,
        isLoading: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to fetch versions',
        isLoading: false,
      });
    }
  },

  fetchVersion: async (skillId: string, versionNumber: number) => {
    set({ isLoading: true, error: null });
    try {
      const version = await skillsApi.getVersion(skillId, versionNumber);
      set({ selectedVersion: version, isLoading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to fetch version',
        isLoading: false,
      });
    }
  },

  activateVersion: async (skillId: string, versionNumber: number) => {
    set({ isLoading: true, error: null });
    try {
      await skillsApi.activateVersion(skillId, versionNumber);
      // Refresh skill data to show updated active version
      await get().fetchSkill(skillId);
      set({ isLoading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to activate version',
        isLoading: false,
      });
      throw err;
    }
  },

  fetchDiff: async (skillId: string, fromVersion: number, toVersion: number) => {
    set({ isLoading: true, error: null });
    try {
      const diff = await skillsApi.diffVersions(skillId, fromVersion, toVersion);
      set({ diffResult: diff, isLoading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to fetch diff',
        isLoading: false,
      });
    }
  },

  clearDiff: () => {
    set({ diffResult: null });
  },

  // Metrics actions
  fetchMetrics: async (skillId: string) => {
    try {
      const metrics = await skillsApi.getMetrics(skillId);
      set({ metrics });
    } catch (err) {
      // Metrics are optional, don't show error
      console.warn('Failed to fetch metrics:', err);
      set({ metrics: null });
    }
  },

  // Utility actions
  clearSelection: () => {
    set({
      selectedSkill: null,
      selectedVersion: null,
      versions: [],
      versionsTotal: 0,
      diffResult: null,
      metrics: null,
    });
  },

  setError: (error: string | null) => set({ error }),
}));
