import React, { useEffect, useState } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { ProtectedRoute } from '../../auth/ProtectedRoute';
import { studentApi } from '../api';
import { Run, Question, Version } from '../../shared/types';
import { RunList } from '../components/RunList';
import { RunDetails } from '../components/RunDetails';
import { QuestionView } from '../components/QuestionView';
import { ReplayViewer } from '../components/ReplayViewer';
import { Loading } from '../../shared/ui/Loading';
import { ErrorMessage } from '../../shared/ui/ErrorMessage';

export const StudentDashboardContent: React.FC = () => {
  const { username, logout } = useAuth();
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [replay, setReplay] = useState<Version[]>([]);

  const [loading, setLoading] = useState(true);
  const [advancing, setAdvancing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRuns = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await studentApi.getRuns();
      setRuns(data);
      if (data.length > 0 && !selectedRun) {
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
        studentApi.getRun(runId),
        studentApi.getRunQuestions(runId),
        studentApi.getReplay(runId),
      ]);
      setSelectedRun(runData);
      setQuestions(qData);
      setReplay(rData);
    } catch (err: any) {
      setError(err.message || `Failed to fetch details for run ${runId}`);
    }
  };

  const handleAdvanceRun = async () => {
    if (!selectedRun) return;
    try {
      setAdvancing(true);
      setError(null);
      await studentApi.advanceRun(selectedRun.id);
      // Refresh run details, questions, and replay after advancement
      await handleSelectRun(selectedRun.id);
      // Refresh runs list to update state badge
      const updatedRuns = await studentApi.getRuns();
      setRuns(updatedRuns);
    } catch (err: any) {
      setError(err.message || 'Failed to advance run');
    } finally {
      setAdvancing(false);
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
            Student Portal
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

      {loading ? (
        <Loading message="Loading student dashboard..." />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1.5rem' }}>
          <div>
            <h3 style={{ margin: '0 0 0.8rem', color: '#111827', fontSize: '1.1rem' }}>
              Available Runs
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
                <QuestionView questions={questions} />
                <ReplayViewer replay={replay} />
              </>
            ) : (
              <div style={{ color: '#6b7280', textAlign: 'center', padding: '2rem' }}>
                Select a run from the list to view details.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export const StudentDashboard: React.FC = () => {
  return (
    <ProtectedRoute requiredRole="student">
      <StudentDashboardContent />
    </ProtectedRoute>
  );
};
