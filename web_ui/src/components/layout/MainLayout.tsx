import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { useSettingsStore } from '@/stores';
import { useEffect } from 'react';

export function MainLayout() {
  const darkMode = useSettingsStore((state) => state.darkMode);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  return (
    <div className="relative flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
