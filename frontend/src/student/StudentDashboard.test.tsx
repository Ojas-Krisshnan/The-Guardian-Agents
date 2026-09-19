import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { StudentDashboard } from './pages/StudentDashboard';
import { AuthProvider } from '../auth/AuthContext';
import { studentApi } from './api';
import { Run, Question, Version } from '../shared/types';

describe('Student Workflow & Dashboard Tests', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('synapse_token', 'token_student_123');
    localStorage.setItem('synapse_role', 'student');
    localStorage.setItem('synapse_user', 'student');
    vi.restoreAllMocks();
  });

  const renderDashboard = () =>
    render(
      <AuthProvider>
        <StudentDashboard />
      </AuthProvider>
    );

  const mockRun: Run = {
    id: 'run_student_1',
    domain: 'demo',
    state: 'drafting',
    created_at: 1000,
    updated_at: 1000,
    meta: { key: 'value' },
  };

  it('Test A: Student dashboard renders header for student role', async () => {
    vi.spyOn(studentApi, 'getRuns').mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Student Portal')).toBeInTheDocument();
      expect(screen.getByText(/Logged in as:/i)).toBeInTheDocument();
    });
  });

  it('Test B: Run list renders available runs', async () => {
    vi.spyOn(studentApi, 'getRuns').mockResolvedValue([mockRun]);
    vi.spyOn(studentApi, 'getRun').mockResolvedValue(mockRun);
    vi.spyOn(studentApi, 'getRunQuestions').mockResolvedValue([]);
    vi.spyOn(studentApi, 'getReplay').mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('run_student_1')).toBeInTheDocument();
      expect(screen.getByText('Domain: demo')).toBeInTheDocument();
    });
  });

  it('Test C: Select run displays run details', async () => {
    vi.spyOn(studentApi, 'getRuns').mockResolvedValue([mockRun]);
    vi.spyOn(studentApi, 'getRun').mockResolvedValue(mockRun);
    vi.spyOn(studentApi, 'getRunQuestions').mockResolvedValue([]);
    vi.spyOn(studentApi, 'getReplay').mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Run: run_student_1')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Advance Run/i })).toBeInTheDocument();
    });
  });

  it('Test D: Advance button calls advanceRun API and updates UI', async () => {
    const completedRun: Run = { ...mockRun, state: 'complete' };

    vi.spyOn(studentApi, 'getRuns').mockResolvedValue([mockRun]);
    vi.spyOn(studentApi, 'getRun')
      .mockResolvedValueOnce(mockRun)
      .mockResolvedValueOnce(completedRun);
    vi.spyOn(studentApi, 'getRunQuestions').mockResolvedValue([]);
    vi.spyOn(studentApi, 'getReplay').mockResolvedValue([]);
    const advanceSpy = vi.spyOn(studentApi, 'advanceRun').mockResolvedValue(completedRun);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Advance Run/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Advance Run/i }));

    await waitFor(() => {
      expect(advanceSpy).toHaveBeenCalledWith('run_student_1');
      expect(screen.getByText('Run completed')).toBeInTheDocument();
    });
  });

  it('Test E: Pending question displays waiting status and NO answer form', async () => {
    const pendingQ: Question = {
      id: 'q_123',
      run_id: 'run_student_1',
      question: 'Needs mentor review?',
      context: {},
      asked_at: 1000,
      timeout_at: 2000,
      answered_at: null,
      answer: null,
      is_answered: false,
      is_expired: false,
    };

    vi.spyOn(studentApi, 'getRuns').mockResolvedValue([mockRun]);
    vi.spyOn(studentApi, 'getRun').mockResolvedValue(mockRun);
    vi.spyOn(studentApi, 'getRunQuestions').mockResolvedValue([pendingQ]);
    vi.spyOn(studentApi, 'getReplay').mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Waiting for expert response')).toBeInTheDocument();
      expect(screen.getByText('Needs mentor review?')).toBeInTheDocument();
      // Verify NO submit/answer button is present for student
      expect(screen.queryByRole('button', { name: /submit answer/i })).not.toBeInTheDocument();
    });
  });

  it('Test F: Completed run displays Run completed banner', async () => {
    const completeRun: Run = { ...mockRun, state: 'complete' };

    vi.spyOn(studentApi, 'getRuns').mockResolvedValue([completeRun]);
    vi.spyOn(studentApi, 'getRun').mockResolvedValue(completeRun);
    vi.spyOn(studentApi, 'getRunQuestions').mockResolvedValue([]);
    vi.spyOn(studentApi, 'getReplay').mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Run completed')).toBeInTheDocument();
    });
  });

  it('Test G: Replay viewer displays history records', async () => {
    const mockReplay: Version[] = [
      { seq: 1, kind: 'opportunity', produced_by: 'agent:spot', payload: { problem: 'test' }, created_at: 1000 },
    ];

    vi.spyOn(studentApi, 'getRuns').mockResolvedValue([mockRun]);
    vi.spyOn(studentApi, 'getRun').mockResolvedValue(mockRun);
    vi.spyOn(studentApi, 'getRunQuestions').mockResolvedValue([]);
    vi.spyOn(studentApi, 'getReplay').mockResolvedValue(mockReplay);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Replay History')).toBeInTheDocument();
      expect(screen.getByText('#1 — opportunity')).toBeInTheDocument();
      expect(screen.getByText('By: agent:spot')).toBeInTheDocument();
    });
  });

  it('Test H: Error message displayed on API failure', async () => {
    vi.spyOn(studentApi, 'getRuns').mockRejectedValue(new Error('Network Error'));

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Network Error')).toBeInTheDocument();
    });
  });
});
