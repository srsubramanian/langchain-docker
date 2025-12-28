import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type AppMode = 'chat' | 'multi_agent';

interface SettingsState {
  // Model settings
  provider: string;
  model: string | null;
  temperature: number;

  // Mode settings
  mode: AppMode;
  agentPreset: string;

  // UI settings
  darkMode: boolean;

  // Actions
  setProvider: (provider: string) => void;
  setModel: (model: string | null) => void;
  setTemperature: (temperature: number) => void;
  setMode: (mode: AppMode) => void;
  setAgentPreset: (preset: string) => void;
  setDarkMode: (darkMode: boolean) => void;
  reset: () => void;
}

const defaultSettings = {
  provider: 'openai',
  model: null,
  temperature: 0.7,
  mode: 'chat' as AppMode,
  agentPreset: 'all',
  darkMode: true,
};

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      ...defaultSettings,

      setProvider: (provider) => set({ provider, model: null }),
      setModel: (model) => set({ model }),
      setTemperature: (temperature) => set({ temperature }),
      setMode: (mode) => set({ mode }),
      setAgentPreset: (agentPreset) => set({ agentPreset }),
      setDarkMode: (darkMode) => set({ darkMode }),
      reset: () => set(defaultSettings),
    }),
    {
      name: 'langchain-settings',
    }
  )
);
