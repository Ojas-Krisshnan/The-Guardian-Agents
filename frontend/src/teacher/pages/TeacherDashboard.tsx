import React, { useEffect, useState } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { ProtectedRoute } from '../../auth/ProtectedRoute';
import { teacherApi } from '../api';
import { Run, Question, Version } from '../../shared/types';
import { RunList } from '../components/RunList';
import { RunDetails } from '../components/RunDetails';
import { QuestionList } from '../components/QuestionList';
import { ReplayViewer } from '../components/ReplayViewer';
import { Loading } from '../../shared/ui/Loading';
import { ErrorMessage } from '../../shared/ui/ErrorMessage';

export const TeacherDashboardContent: React.FC = () => {
  const { username, logout } = useAuth();
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [replay, setReplay] = useState<Version[]>([]);

  const [newDomain, setNewDomain] = useState('demo');
  const [newMeta, setNewMeta] = useState('');

  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [answering, setAnswering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRuns = async (selectId?: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await teacherApi.getRuns();
      setRuns(data);
      if (selectId) {
        handleSelectRun(selectId);
      } else if (data.length > 0 && !selectedRun) {
        handleSelectRun(data[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch runs');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectRun = async (runId: string) => {
    try {
      setError(null);
      const [runData, qData, rData] = await Promise.all([
        teacherApi.getRun(runId),
        teacherApi.getRunQuestions(runId),
        teacherApi.getReplay(runId),
      ]);
      setSelectedRun(runData);
      setQuestions(qData);
      setReplay(rData);
    } catch (err: any) {
      setError(err.message || `Failed to fetch details for run ${runId}`);
    }
  };

  const handleCreateRun = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setCreating(true);
      setError(null);
      let parsedMeta: Record<string, any> = {};
      if (newMeta.trim()) {
        try {
          parsedMeta = JSON.parse(newMeta);
        } catch {
          parsedMeta = { note: newMeta.trim() };
        }
      }
      const created = await teacherApi.createRun(newDomain || 'demo', parsedMeta);
      setNewMeta('');
      await fetchRuns(created.id);
    } catch (err: any) {
      setError(err.message || 'Failed to create run');
    } finally {
      setCreating(false);
    }
  };

  const handleAdvanceRun = async () => {
    if (!selectedRun) return;
    try {
      setAdvancing(true);
      setError(null);
      await teacherApi.advanceRun(selectedRun.id);
      await handleSelectRun(selectedRun.id);
      const updatedRuns = await teacherApi.getRuns();
      setRuns(updatedRuns);
    } catch (err: any) {
      setError(err.message || 'Failed to advance run');
    } finally {
      setAdvancing(false);
    }
  };

  const handleAnswerSubmit = async (questionId: string, answerText: string) => {
    if (!selectedRun) return;
    try {
      setAnswering(true);
      setError(null);
      await teacherApi.answerQuestion(questionId, answerText, username || 'teacher');
      await handleSelectRun(selectedRun.id);
      const updatedRuns = await teacherApi.getRuns();
      setRuns(updatedRuns);
    } catch (err: any) {
      setError(err.message || 'Failed to submit answer');
    } finally {
      setAnswering(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  return (
    <div
      style={{
        maxWidth: '1000px',
        margin: '0 auto',
        padding: '1.5rem',
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid #e5e7eb',
          paddingBottom: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', color: '#111827' }}>
            Teacher Portal
          </h1>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: '0.2rem' }}>
            Logged in as: <strong>{username}</strong>
          </div>
        </div>
        <button
          onClick={logout}
          style={{
            padding: '0.5rem 1rem',
            backgroundColor: '#ef4444',
            color: '#ffffff',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontWeight: 500,
          }}
        >
          Logout
        </button>
      </header>

      {error && <ErrorMessage message={error} />}

      {/* Create Run Form Section */}
      <div
        style={{
          padding: '1rem 1.2rem',
          border: '1px solid #e5e7eb',
          borderRadius: '8px',
          backgroundColor: '#f9fafb',
          marginBottom: '1.5rem',
        }}
      >
        <h3 style={{ margin: '0 0 0.8rem', fontSize: '1.05rem', color: '#111827' }}>
          Create New Run
        </h3>
        <form
          onSubmit={handleCreateRun}
          style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}
        >
          <div style={{ flex: '1 1 200px' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', color: '#374151', marginBottom: '0.3rem' }}>
              Domain
            </label>
            <input
              type="text"
              value={newDomain}
              onChange={(e) => setNewDomain(e.target.value)}
              placeholder="demo"
              style={{
                width: '100%',
                padding: '0.5rem 0.7rem',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontSize: '0.85rem',
              }}
            />
          </div>
          <div style={{ flex: '2 1 300px' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', color: '#374151', marginBottom: '0.3rem' }}>
              Metadata (optional JSON or text note)
            </label>
            <input
              type="text"
              value={newMeta}
              onChange={(e) => setNewMeta(e.target.value)}
              placeholder='e.g. {"course": "CS101"}'
              style={{
                width: '100%',
                padding: '0.5rem 0.7rem',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontSize: '0.85rem',
              }}
            />
          </div>
          <button
            type="submit"
            disabled={creating}
            style={{
              padding: '0.55rem 1.2rem',
              backgroundColor: '#059669',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 600,
              cursor: creating ? 'not-allowed' : 'pointer',
            }}
          >
            {creating ? 'Creating...' : 'Create Run'}
          </button>
        </form>
      </div>

      {loading ? (
        <Loading message="Loading teacher portal..." />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1.5rem' }}>
          <div>
            <h3 style={{ margin: '0 0 0.8rem', color: '#111827', fontSize: '1.1rem' }}>
              All Runs
            </h3>
            <RunList
              runs={runs}
              selectedRunId={selectedRun?.id || null}
              onSelectRun={handleSelectRun}
            />
          </div>

          <div>
            {selectedRun ? (
              <>
                <RunDetails
                  run={selectedRun}
                  onAdvance={handleAdvanceRun}
                  advancing={advancing}
                />
                <QuestionList
                  questions={questions}
                  onAnswerSubmit={handleAnswerSubmit}
                  answering={answering}
                />
                <ReplayViewer replay={replay} />
              </>
            ) : (
              <div style={{ color: '#6b7280', textAlign: 'center', padding: '2rem' }}>
                Select a run to manage questions and view history.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export const TeacherDashboard: React.FC = () => {
  return (
    <ProtectedRoute requiredRole="teacher">
      <TeacherDashboardContent />
    </ProtectedRoute>
  );
};
