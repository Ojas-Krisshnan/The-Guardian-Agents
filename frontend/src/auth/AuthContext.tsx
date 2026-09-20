import React, { createContext, useContext, useState, useEffect } from 'react';
import { UserRole } from '../shared/types';
import { login as apiLogin } from '../api/auth';

interface AuthContextType {
  token: string | null;
  role: UserRole | null;
  username: string | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('synapse_token'));
  const [role, setRole] = useState<UserRole | null>(() => (localStorage.getItem('synapse_role') as UserRole) || null);
  const [username, setUsername] = useState<string | null>(() => localStorage.getItem('synapse_user'));

  useEffect(() => {
    if (token) {
      localStorage.setItem('synapse_token', token);
    } else {
      localStorage.removeItem('synapse_token');
    }
  }, [token]);

  useEffect(() => {
    if (role) {
      localStorage.setItem('synapse_role', role);
    } else {
      localStorage.removeItem('synapse_role');
    }
  }, [role]);

  useEffect(() => {
    if (username) {
      localStorage.setItem('synapse_user', username);
    } else {
      localStorage.removeItem('synapse_user');
    }
  }, [username]);

  const handleLogin = async (u: string, p: string) => {
    const res = await apiLogin(u, p);
    setToken(res.access_token);
    setRole(res.role);
    setUsername(u);
  };

  const handleLogout = () => {
    setToken(null);
    setRole(null);
    setUsername(null);
    localStorage.removeItem('synapse_token');
    localStorage.removeItem('synapse_role');
    localStorage.removeItem('synapse_user');
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        role,
        username,
        isAuthenticated: !!token,
        login: handleLogin,
        logout: handleLogout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
};
