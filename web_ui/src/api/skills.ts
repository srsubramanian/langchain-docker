/**
 * Skills API client implementing progressive disclosure pattern.
 * Based on Anthropic's Agent Skills architecture.
 */

import type {
  SkillCreateRequest,
  SkillCreateResponse,
  SkillDeleteResponse,
  SkillInfo,
  SkillListResponse,
  SkillLoadResponse,
  SkillUpdateRequest,
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
}

export const skillsApi = new SkillsApi();
