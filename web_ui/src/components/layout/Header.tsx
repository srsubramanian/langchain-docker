import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { MessageSquare, Users, Wrench, Sun, Moon, Bot, Sparkles, ChevronDown, Plus, Check, BookOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useSettingsStore } from '@/stores';
import { useUserStore } from '@/stores/userStore';
import { cn } from '@/lib/cn';

const navigation = [
  { name: 'Agents', href: '/agents', icon: Bot },
  { name: 'Skills', href: '/skills', icon: Sparkles },
  { name: 'Knowledge', href: '/knowledge-base', icon: BookOpen },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
  { name: 'Multi-Agent', href: '/multi-agent', icon: Users },
  { name: 'Builder', href: '/builder', icon: Wrench },
];

export function Header() {
  const location = useLocation();
  const { darkMode, setDarkMode } = useSettingsStore();
  const { currentUserId, currentUserName, users, setCurrentUser, addUser } = useUserStore();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUserName, setNewUserName] = useState('');

  const currentUser = users.find((u) => u.id === currentUserId);

  const handleAddUser = () => {
    if (newUserName.trim()) {
      addUser(newUserName.trim());
      setNewUserName('');
      setShowAddUser(false);
      setShowUserMenu(false);
    }
  };

  const handleSelectUser = (userId: string) => {
    setCurrentUser(userId);
    setShowUserMenu(false);
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center">
        <div className="mr-4 flex">
          <Link to="/" className="mr-6 flex items-center space-x-2">
            <div className="h-6 w-6 rounded bg-primary flex items-center justify-center">
              <span className="text-xs font-bold text-primary-foreground">LC</span>
            </div>
            <span className="font-bold">LangChain Docker</span>
          </Link>
          <nav className="flex items-center space-x-6 text-sm font-medium">
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.href;
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    'flex items-center gap-2 transition-colors hover:text-foreground/80',
                    isActive ? 'text-foreground' : 'text-foreground/60'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.name}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex flex-1 items-center justify-end space-x-2">
          {/* User Selector Dropdown */}
          <div className="relative">
            <Button
              variant="ghost"
              size="sm"
              className="flex items-center gap-2"
              onClick={() => setShowUserMenu(!showUserMenu)}
            >
              <div className={cn('h-6 w-6 rounded-full flex items-center justify-center text-white text-xs font-medium', currentUser?.color || 'bg-gray-500')}>
                {currentUserName.charAt(0).toUpperCase()}
              </div>
              <span className="text-sm">{currentUserName}</span>
              <ChevronDown className="h-3 w-3" />
            </Button>

            {showUserMenu && (
              <>
                {/* Backdrop to close menu */}
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => {
                    setShowUserMenu(false);
                    setShowAddUser(false);
                  }}
                />
                {/* Dropdown menu */}
                <div className="absolute right-0 top-full mt-1 w-56 rounded-md border bg-popover shadow-lg z-50">
                  <div className="p-2">
                    <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                      Switch User
                    </div>
                    {users.map((user) => (
                      <button
                        key={user.id}
                        onClick={() => handleSelectUser(user.id)}
                        className={cn(
                          'w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded-sm hover:bg-accent',
                          user.id === currentUserId && 'bg-accent'
                        )}
                      >
                        <div className={cn('h-6 w-6 rounded-full flex items-center justify-center text-white text-xs font-medium', user.color)}>
                          {user.name.charAt(0).toUpperCase()}
                        </div>
                        <span className="flex-1 text-left">{user.name}</span>
                        {user.id === currentUserId && (
                          <Check className="h-4 w-4 text-primary" />
                        )}
                      </button>
                    ))}
                    <div className="my-1 border-t" />
                    {showAddUser ? (
                      <div className="p-2">
                        <div className="flex gap-2">
                          <Input
                            placeholder="Enter name..."
                            value={newUserName}
                            onChange={(e) => setNewUserName(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleAddUser()}
                            className="h-8 text-sm"
                            autoFocus
                          />
                          <Button size="sm" className="h-8" onClick={handleAddUser}>
                            Add
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => setShowAddUser(true)}
                        className="w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded-sm hover:bg-accent text-muted-foreground"
                      >
                        <Plus className="h-4 w-4" />
                        <span>Add New User</span>
                      </button>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>

          <Button
            variant="ghost"
            size="icon"
            onClick={() => setDarkMode(!darkMode)}
          >
            {darkMode ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
    </header>
  );
}
