import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import App from './App';
import * as authApi from './api/auth';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { AuthProvider } from './auth/AuthContext';

describe('Frontend Foundation Auth Tests', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('Test A: Login API function calls correct endpoint', async () => {
    const loginSpy = vi.spyOn(authApi, 'login').mockResolvedValue({
      access_token: 'fake_jwt_token',
      token_type: 'bearer',
      role: 'teacher',
    });

    render(<App />);

    fireEvent.change(screen.getByPlaceholderText('teacher or student'), {
      target: { value: 'teacher' },
    });
    fireEvent.change(screen.getByPlaceholderText('teacher123 or student123'), {
      target: { value: 'teacher123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(loginSpy).toHaveBeenCalledWith('teacher', 'teacher123');
    });
  });

  it('Test B: Successful login stores authentication state', async () => {
    vi.spyOn(authApi, 'login').mockResolvedValue({
      access_token: 'token_teacher_123',
      token_type: 'bearer',
      role: 'teacher',
    });

    render(<App />);

    fireEvent.change(screen.getByPlaceholderText('teacher or student'), {
      target: { value: 'teacher' },
    });
    fireEvent.change(screen.getByPlaceholderText('teacher123 or student123'), {
      target: { value: 'teacher123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(localStorage.getItem('synapse_token')).toBe('token_teacher_123');
      expect(localStorage.getItem('synapse_role')).toBe('teacher');
      expect(screen.getAllByText(/Teacher Portal/i)[0]).toBeInTheDocument();
    });
  });

  it('Test C: Logout clears authentication state', async () => {
    localStorage.setItem('synapse_token', 'token_teacher_123');
    localStorage.setItem('synapse_role', 'teacher');
    localStorage.setItem('synapse_user', 'teacher');

    render(<App />);

    expect(screen.getAllByText(/Teacher Portal/i)[0]).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /logout/i }));

    expect(localStorage.getItem('synapse_token')).toBeNull();
    expect(localStorage.getItem('synapse_role')).toBeNull();
    expect(screen.getByPlaceholderText('teacher or student')).toBeInTheDocument();
  });

  it('Test D: Unauthenticated protected route rejects access', () => {
    render(
      <AuthProvider>
        <ProtectedRoute requiredRole="teacher">
          <div>Secret Content</div>
        </ProtectedRoute>
      </AuthProvider>
    );

    expect(screen.getByText(/Please log in to access this page/i)).toBeInTheDocument();
    expect(screen.queryByText('Secret Content')).not.toBeInTheDocument();
  });

  it('Test E: Role-protected route rejects wrong role', () => {
    localStorage.setItem('synapse_token', 'token_student_123');
    localStorage.setItem('synapse_role', 'student');
    localStorage.setItem('synapse_user', 'student');

    render(
      <AuthProvider>
        <ProtectedRoute requiredRole="teacher">
          <div>Teacher Only Content</div>
        </ProtectedRoute>
      </AuthProvider>
    );

    expect(screen.getByText(/Access Denied/i)).toBeInTheDocument();
    expect(screen.queryByText('Teacher Only Content')).not.toBeInTheDocument();
  });
});
