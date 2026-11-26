import { useState, useEffect, createContext, useContext, ReactNode } from 'react';
import { api } from '../lib/api';
import type { User } from '../types';
import { toast } from 'sonner';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login: (credentials: { email: string; password: string }) => Promise<User>;
  signup: (data: { nom_utilisateur: string; email: string; password: string; domaine: string }) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchUser = async () => {
    try {
      const u = await api.getMe();
      setUser(u);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchUser();

    const handleExpired = (e: any) => {
      setUser(null);
      toast.error(e.detail?.message || 'Votre session a expiré. Veuillez vous reconnecter.');
    };

    window.addEventListener('auth:expired', handleExpired);
    return () => window.removeEventListener('auth:expired', handleExpired);
  }, []);

  const login = async (credentials: { email: string; password: string }): Promise<User> => {
    const loggedUser = await api.login(credentials);
    setUser(loggedUser);
    return loggedUser;
  };

  const signup = async (data: { nom_utilisateur: string; email: string; password: string; domaine: string }): Promise<void> => {
    await api.signup(data);
  };

  const logout = async () => {
    await api.logout();
    setUser(null);
    toast.success('Déconnexion réussie');
  };

  const refreshUser = async () => {
    await fetchUser();
  };

  const isAuthenticated = !!user;
  const isAdmin = user?.role === 'administrateur';

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated,
        isAdmin,
        login,
        signup,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
