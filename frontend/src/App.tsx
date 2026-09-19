import React, { useState } from 'react';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { StudentDashboard } from './student/pages/StudentDashboard';
import { TeacherDashboard } from './teacher/pages/TeacherDashboard';
import { ErrorMessage } from './shared/ui/ErrorMessage';

const LoginView: React.FC = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '80vh',
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '380px',
          padding: '2rem',
          border: '1px solid #e5e7eb',
          borderRadius: '10px',
          boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
          backgroundColor: '#ffffff',
        }}
      >
        <h2 style={{ margin: '0 0 0.5rem', textAlign: 'center', color: '#111827' }}>
          Synapse Cycle
        </h2>
        <p style={{ margin: '0 0 1.5rem', textAlign: 'center', color: '#6b7280', fontSize: '0.9rem' }}>
          Sign in to your account
        </p>

        {error && <ErrorMessage message={error} />}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1rem' }}>
            <label
              htmlFor="username"
              style={{ display: 'block', marginBottom: '0.4rem', fontSize: '0.85rem', color: '#374151' }}
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              placeholder="teacher or student"
              style={{
                width: '100%',
                padding: '0.6rem 0.8rem',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label
              htmlFor="password"
              style={{ display: 'block', marginBottom: '0.4rem', fontSize: '0.85rem', color: '#374151' }}
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="teacher123 or student123"
              style={{
                width: '100%',
                padding: '0.6rem 0.8rem',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '0.7rem',
              backgroundColor: '#2563eb',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
};

export const DashboardRouter: React.FC = () => {
  const { role } = useAuth();
  if (role === 'student') {
    return <StudentDashboard />;
  }
  return <TeacherDashboard />;
};

export const AppContent: React.FC = () => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <DashboardRouter /> : <LoginView />;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;
