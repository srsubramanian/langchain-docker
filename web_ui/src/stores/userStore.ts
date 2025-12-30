import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface User {
  id: string;
  name: string;
  color: string;
}

// Predefined colors for user avatars
const USER_COLORS = [
  'bg-violet-500',
  'bg-blue-500',
  'bg-cyan-500',
  'bg-teal-500',
  'bg-green-500',
  'bg-amber-500',
  'bg-orange-500',
  'bg-rose-500',
  'bg-pink-500',
  'bg-indigo-500',
];

function getRandomColor(): string {
  return USER_COLORS[Math.floor(Math.random() * USER_COLORS.length)];
}

function generateUserId(): string {
  return `user_${crypto.randomUUID().slice(0, 8)}`;
}

// Default users for easy testing
const DEFAULT_USERS: User[] = [
  { id: 'alice', name: 'Alice', color: 'bg-violet-500' },
  { id: 'bob', name: 'Bob', color: 'bg-blue-500' },
  { id: 'charlie', name: 'Charlie', color: 'bg-teal-500' },
];

interface UserState {
  // Current user
  currentUserId: string;
  currentUserName: string;

  // All available users
  users: User[];

  // Actions
  setCurrentUser: (userId: string) => void;
  addUser: (name: string) => User;
  removeUser: (userId: string) => void;
  getCurrentUser: () => User | undefined;
}

export const useUserStore = create<UserState>()(
  persist(
    (set, get) => ({
      // Default to first user
      currentUserId: DEFAULT_USERS[0].id,
      currentUserName: DEFAULT_USERS[0].name,
      users: DEFAULT_USERS,

      setCurrentUser: (userId: string) => {
        const user = get().users.find((u) => u.id === userId);
        if (user) {
          set({ currentUserId: user.id, currentUserName: user.name });
        }
      },

      addUser: (name: string) => {
        const newUser: User = {
          id: generateUserId(),
          name: name.trim(),
          color: getRandomColor(),
        };
        set((state) => ({
          users: [...state.users, newUser],
          currentUserId: newUser.id,
          currentUserName: newUser.name,
        }));
        return newUser;
      },

      removeUser: (userId: string) => {
        const state = get();
        // Don't remove if it's the last user
        if (state.users.length <= 1) return;

        // Don't remove default users
        if (DEFAULT_USERS.some((u) => u.id === userId)) return;

        const newUsers = state.users.filter((u) => u.id !== userId);
        const wasCurrentUser = state.currentUserId === userId;

        set({
          users: newUsers,
          // If we removed the current user, switch to first user
          ...(wasCurrentUser && {
            currentUserId: newUsers[0].id,
            currentUserName: newUsers[0].name,
          }),
        });
      },

      getCurrentUser: () => {
        const state = get();
        return state.users.find((u) => u.id === state.currentUserId);
      },
    }),
    {
      name: 'user-storage',
    }
  )
);
