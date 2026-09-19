import React from 'react';
import { Run } from '../../shared/types';
import { EmptyState } from '../../shared/ui/EmptyState';

interface RunListProps {
  runs: Run[];
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
}

export const RunList: React.FC<RunListProps> = ({
  runs,
  selectedRunId,
  onSelectRun,
}) => {
  if (runs.length === 0) {
    return <EmptyState message="No runs available" />;
  }

  const getStateColor = (state: string) => {
    switch (state) {
      case 'complete':
        return '#059669';
      case 'failed':
        return '#dc2626';
      case 'awaiting_expert':
        return '#d97706';
      default:
        return '#2563eb';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      {runs.map((run) => {
        const isSelected = run.id === selectedRunId;
        return (
          <div
            key={run.id}
            onClick={() => onSelectRun(run.id)}
            style={{
              padding: '0.85rem 1rem',
              border: `1px solid ${isSelected ? '#2563eb' : '#e5e7eb'}`,
              borderRadius: '8px',
              backgroundColor: isSelected ? '#eff6ff' : '#ffffff',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontWeight: 600, color: '#111827', fontSize: '0.95rem' }}>
                {run.id}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.2rem' }}>
                Domain: {run.domain}
              </div>
            </div>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                padding: '0.25rem 0.6rem',
                borderRadius: '12px',
                color: '#ffffff',
                backgroundColor: getStateColor(run.state),
                textTransform: 'uppercase',
              }}
            >
              {run.state}
            </span>
          </div>
        );
      })}
    </div>
  );
};
