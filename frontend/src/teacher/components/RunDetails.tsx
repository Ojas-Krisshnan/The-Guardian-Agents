import React from 'react';
import { Run } from '../../shared/types';

interface RunDetailsProps {
  run: Run;
  onAdvance: () => void;
  advancing: boolean;
}

export const RunDetails: React.FC<RunDetailsProps> = ({
  run,
  onAdvance,
  advancing,
}) => {
  const isTerminal = run.state === 'complete' || run.state === 'failed';

  return (
    <div
      style={{
        padding: '1.2rem',
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        backgroundColor: '#ffffff',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1rem',
        }}
      >
        <h3 style={{ margin: 0, color: '#111827', fontSize: '1.1rem' }}>
          Run: {run.id}
        </h3>
        <span
          style={{
            fontSize: '0.8rem',
            fontWeight: 600,
            padding: '0.3rem 0.7rem',
            borderRadius: '12px',
            backgroundColor: run.state === 'complete' ? '#d1fae5' : '#e0e7ff',
            color: run.state === 'complete' ? '#065f46' : '#3730a3',
          }}
        >
          {run.state}
        </span>
      </div>

      <div style={{ fontSize: '0.9rem', color: '#4b5563', marginBottom: '1rem' }}>
        <p style={{ margin: '0.3rem 0' }}>
          <strong>Domain:</strong> {run.domain}
        </p>
        <p style={{ margin: '0.3rem 0' }}>
          <strong>State:</strong> {run.state}
        </p>
        {Object.keys(run.meta || {}).length > 0 && (
          <div style={{ marginTop: '0.5rem' }}>
            <strong>Metadata:</strong>
            <pre
              style={{
                margin: '0.3rem 0 0',
                padding: '0.5rem',
                backgroundColor: '#f9fafb',
                borderRadius: '4px',
                fontSize: '0.8rem',
              }}
            >
              {JSON.stringify(run.meta, null, 2)}
            </pre>
          </div>
        )}
      </div>

      <button
        onClick={onAdvance}
        disabled={advancing || isTerminal}
        style={{
          width: '100%',
          padding: '0.65rem',
          backgroundColor: isTerminal ? '#9ca3af' : '#2563eb',
          color: '#ffffff',
          border: 'none',
          borderRadius: '6px',
          fontWeight: 600,
          cursor: advancing || isTerminal ? 'not-allowed' : 'pointer',
        }}
      >
        {advancing ? 'Advancing Run...' : isTerminal ? 'Run Finished' : 'Advance Run'}
      </button>
    </div>
  );
};
