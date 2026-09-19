import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TeacherDashboard } from './pages/TeacherDashboard';
import { AuthProvider } from '../auth/AuthContext';
import { teacherApi } from './api';
import { Run, Question, Version } from '../shared/types';

describe('Teacher / Expert Dashboard Tests', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('synapse_token', 'token_teacher_123');
    localStorage.setItem('synapse_role', 'teacher');
    localStorage.setItem('synapse_user', 'teacher');
    vi.restoreAllMocks();
  });

  const renderDashboard = () =>
    render(
      <AuthProvider>
        <TeacherDashboard />
      </AuthProvider>
    );

  const mockRun: Run = {
    id: 'run_teacher_1',
    domain: 'demo',
    state: 'drafting',
    created_at: 1000,
    updated_at: 1000,
    meta: { course: 'CS101' },
  };

  it('TEST A: Teacher dashboard renders Teacher Portal and username', async () => {
    vi.spyOn(teacherApi, 'getRuns').mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Teacher Portal')).toBeInTheDocument();
      expect(screen.getByText('teacher')).toBeInTheDocument();
    });
  });

  it('TEST B: Teacher can see the run list', async () => {
    vi.spyOn(teacherApi, 'getRuns').mockResolvedValue([mockRun]);
    vi.spyOn(teacherApi, 'getRun').mockResolvedValue(mockRun);
    vi.spyOn(teacherApi, 'getRunQuestions').mockResolvedValue([]);
    vi.spyOn(teacherApi, 'getReplay').mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('run_teacher_1')).toBeInTheDocument();
      expect(screen.getByText('Domain: demo')).toBeInTheDocument();
    });
  });

  it('TEST C: Teacher can create a run', async () => {
    const newRun: Run = {
      id: 'run_teacher_2',
      domain: 'biology',
      state: 'drafting',
      created_at: 2000,
      updated_at: 2000,
      meta: {},
    };

    vi.spyOn(teacherApi, 'getRuns')
      .mockResolvedValueOnce([mockRun])
      .mockResolvedValueOnce([mockRun, newRun]);
    vi.spyOn(teacherApi, 'getRun').mockResolvedValue(newRun);
    vi.spyOn(teacherApi, 'getRunQuestions').mockResolvedValue([]);
    vi.spyOn(teacherApi, 'getReplay').mockResolvedValue([]);
    const createSpy = vi.spyOn(teacherApi, 'createRun').mockResolvedValue(newRun);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Create Run/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Create Run/i }));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith('demo', {});
    });
  });

  it('TEST D: Selecting a run displays its details', async () => {
    vi.spyOn(teacherApi, 'getRuns').mockResolvedValue([mockRun]);
    vi.spyOn(teacherApi, 'getRun').mockResolvedValue(mockRun);
    vi.spyOn(teacherApi, 'getRunQuestions').mockResolvedValue([]);
    vi.spyOn(teacherApi, 'getReplay').mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Run: run_teacher_1')).toBeInTheDocument();
    });
  });

  it('TEST E: Teacher can advance a run', async () => {
    const completedRun: Run = { ...mockRun, state: 'complete' };

    vi.spyOn(teacherApi, 'getRuns').mockResolvedValue([mockRun]);
    vi.spyOn(teacherApi, 'getRun')
      .mockResolvedValueOnce(mockRun)
      .mockResolvedValueOnce(completedRun);
    vi.spyOn(teacherApi, 'getRunQuestions').mockResolvedValue([]);
    vi.spyOn(teacherApi, 'getReplay').mockResolvedValue([]);
    const advanceSpy = vi.spyOn(teacherApi, 'advanceRun').mockResolvedValue(completedRun);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Advance Run/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Advance Run/i }));

    await waitFor(() => {
      expect(advanceSpy).toHaveBeenCalledWith('run_teacher_1');
    });
  });

  it('TEST F: Pending expert question is displayed', async () => {
    const pendingQ: Question = {
      id: 'q_t1',
      run_id: 'run_teacher_1',
      question: 'Evaluate source credibility?',
      context: {},
      asked_at: 1000,
      timeout_at: 2000,
      answered_at: null,
      answer: null,
      is_answered: false,
      is_expired: false,
    };

    vi.spyOn(teacherApi, 'getRuns').mockResolvedValue([mockRun]);
    vi.spyOn(teacherApi, 'getRun').mockResolvedValue(mockRun);
    vi.spyOn(teacherApi, 'getRunQuestions').mockResolvedValue([pendingQ]);
    vi.spyOn(teacherApi, 'getReplay').mockResolvedValue([]);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Pending Expert Question (q_t1)')).toBeInTheDocument();
      expect(screen.getByText('Evaluate source credibility?')).toBeInTheDocument();
    });
  });

  it('TEST G & H: Teacher can submit answer and status changes to answered', async () => {
    const pendingQ: Question = {
      id: 'q_t1',
      run_id: 'run_teacher_1',
      question: 'Evaluate source credibility?',
      context: {},
      asked_at: 1000,
      timeout_at: 2000,
      answered_at: null,
      answer: null,
      is_answered: false,
      is_expired: false,
    };

    const answeredQ: Question = {
      ...pendingQ,
      answered_at: 1500,
      answer: 'Credibility confirmed',
      is_answered: true,
    };

    vi.spyOn(teacherApi, 'getRuns').mockResolvedValue([mockRun]);
    vi.spyOn(teacherApi, 'getRun').mockResolvedValue(mockRun);
    vi.spyOn(teacherApi, 'getRunQuestions')
      .mockResolvedValueOnce([pendingQ])
      .mockResolvedValueOnce([answeredQ]);
    vi.spyOn(teacherApi, 'getReplay').mockResolvedValue([]);
    const answerSpy = vi.spyOn(teacherApi, 'answerQuestion').mockResolvedValue(answeredQ);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type expert guidance/answer...')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText('Type expert guidance/answer...'), {
      target: { value: 'Credibility confirmed' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Answer Question/i }));

    await waitFor(() => {
      expect(answerSpy).toHaveBeenCalledWith('q_t1', 'Credibility confirmed', 'teacher');
      expect(screen.getByText('STATUS: ANSWERED')).toBeInTheDocument();
      expect(screen.getByText('Credibility confirmed')).toBeInTheDocument();
    });
  });

  it('TEST I: Replay history is displayed', async () => {
    const mockReplay: Version[] = [
      { seq: 1, kind: 'opportunity', produced_by: 'agent:spot', payload: { data: 'test' }, created_at: 1000 },
    ];

    vi.spyOn(teacherApi, 'getRuns').mockResolvedValue([mockRun]);
    vi.spyOn(teacherApi, 'getRun').mockResolvedValue(mockRun);
    vi.spyOn(teacherApi, 'getRunQuestions').mockResolvedValue([]);
    vi.spyOn(teacherApi, 'getReplay').mockResolvedValue(mockReplay);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Replay History')).toBeInTheDocument();
      expect(screen.getByText('#1 — opportunity')).toBeInTheDocument();
    });
  });

  it('TEST J: API failure displays ErrorMessage component', async () => {
    vi.spyOn(teacherApi, 'getRuns').mockRejectedValue(new Error('Backend Connection Failed'));

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Backend Connection Failed')).toBeInTheDocument();
    });
  });

  it('TEST K: Student role does NOT render TeacherDashboard', async () => {
    localStorage.setItem('synapse_token', 'token_student_123');
    localStorage.setItem('synapse_role', 'student');
    localStorage.setItem('synapse_user', 'student');

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/Access Denied/i)).toBeInTheDocument();
      expect(screen.queryByText('Create New Run')).not.toBeInTheDocument();
    });
  });
});
