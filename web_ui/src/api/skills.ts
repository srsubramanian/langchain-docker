/**
 * Skills API client implementing progressive disclosure pattern.
 * Based on Anthropic's Agent Skills architecture.
 * Supports versioned skill management with Redis persistence.
 */

import type {
  SkillCreateRequest,
  SkillCreateResponse,
  SkillDeleteResponse,
  SkillDiffResponse,
  SkillInfo,
  SkillListResponse,
  SkillLoadResponse,
  SkillUpdateRequest,
  SkillUsageMetrics,
  SkillVersionDetail,
  SkillVersionListResponse,
  VersionedSkillInfo,
} from '@/types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

class SkillsApi {
  /**
   * List all skills (Level 1 metadata only).
   * Returns minimal metadata for agent system prompts.
   */
  async list(): Promise<SkillListResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/skills`);
    if (!response.ok) {
      throw new Error(`Failed to list skills: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Get full skill information including content.
   * Returns complete skill data for editing.
   */
  async get(skillId: string): Promise<SkillInfo> {
    const response = await fetch(`${API_BASE_URL}/api/v1/skills/${skillId}`);
    if (!response.ok) {
      throw new Error(`Failed to get skill: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Create a new custom skill.
   */
  async create(request: SkillCreateRequest): Promise<SkillCreateResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/skills`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'Failed to create skill');
    }
    return response.json();
  }

  /**
   * Update an existing custom skill.
   */
  async update(skillId: string, request: SkillUpdateRequest): Promise<SkillInfo> {
    const response = await fetch(`${API_BASE_URL}/api/v1/skills/${skillId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'Failed to update skill');
    }
    return response.json();
  }

  /**
   * Delete a custom skill.
   */
  async delete(skillId: string): Promise<SkillDeleteResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/skills/${skillId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'Failed to delete skill');
    }
    return response.json();
  }

  /**
   * Load skill core content (Level 2).
   * Called by agents when they trigger a skill.
   */
  async load(skillId: string): Promise<SkillLoadResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/skills/${skillId}/load`);
    if (!response.ok) {
      throw new Error(`Failed to load skill: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Load a specific skill resource (Level 3).
   * Called by agents when they need additional details.
   */
  async loadResource(skillId: string, resourceName: string): Promise<{ content: string }> {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/skills/${skillId}/resources/${resourceName}`
    );
    if (!response.ok) {
      throw new Error(`Failed to load resource: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Export skill as SKILL.md format.
   */
  async export(skillId: string): Promise<{ content: string }> {
    const response = await fetch(`${API_BASE_URL}/api/v1/skills/${skillId}/export`);
    if (!response.ok) {
      throw new Error(`Failed to export skill: ${response.statusText}`);
    }
    return response.json();
  }

  // ==========================================================================
  // Versioning Methods
  // ==========================================================================

  /**
   * Get skill with full version history.
   * Returns skill info along with version summary and metrics.
   */
  async getVersioned(skillId: string): Promise<VersionedSkillInfo> {
    const response = await fetch(`${API_BASE_URL}/api/v1/skills/${skillId}/versioned`);
    if (!response.ok) {
      throw new Error(`Failed to get versioned skill: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * List all versions of a skill with pagination.
   */
  async listVersions(
    skillId: string,
    limit: number = 20,
    offset: number = 0
  ): Promise<SkillVersionListResponse> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    const response = await fetch(
      `${API_BASE_URL}/api/v1/skills/${skillId}/versions?${params}`
    );
    if (!response.ok) {
      throw new Error(`Failed to list versions: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Get full content of a specific version.
   */
  async getVersion(skillId: string, versionNumber: number): Promise<SkillVersionDetail> {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/skills/${skillId}/versions/${versionNumber}`
    );
    if (!response.ok) {
      throw new Error(`Failed to get version: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Activate a specific version (rollback).
   */
  async activateVersion(
    skillId: string,
    versionNumber: number
  ): Promise<{ skill_id: string; active_version: number; message: string }> {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/skills/${skillId}/versions/${versionNumber}/activate`,
      { method: 'POST' }
    );
    if (!response.ok) {
      throw new Error(`Failed to activate version: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Compare two versions of a skill.
   */
  async diffVersions(
    skillId: string,
    fromVersion: number,
    toVersion: number
  ): Promise<SkillDiffResponse> {
    const params = new URLSearchParams({
      from_version: fromVersion.toString(),
      to_version: toVersion.toString(),
    });
    const response = await fetch(
      `${API_BASE_URL}/api/v1/skills/${skillId}/versions/diff?${params}`
    );
    if (!response.ok) {
      throw new Error(`Failed to diff versions: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Get usage metrics for a skill.
   */
  async getMetrics(skillId: string): Promise<SkillUsageMetrics> {
    const response = await fetch(`${API_BASE_URL}/api/v1/skills/${skillId}/metrics`);
    if (!response.ok) {
      throw new Error(`Failed to get metrics: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Reset a built-in skill to its original file-based content.
   * Clears all Redis versions and custom content.
   */
  async reset(skillId: string): Promise<SkillInfo> {
    const response = await fetch(`${API_BASE_URL}/api/v1/skills/${skillId}/reset`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || 'Failed to reset skill');
    }
    return response.json();
  }
}

export const skillsApi = new SkillsApi();
