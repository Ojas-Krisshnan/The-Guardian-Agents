import React from 'react';
import { Version } from '../../shared/types';
import { EmptyState } from '../../shared/ui/EmptyState';

interface ReplayViewerProps {
  replay: Version[];
}

export const ReplayViewer: React.FC<ReplayViewerProps> = ({ replay }) => {
  if (replay.length === 0) {
    return <EmptyState message="No replay history available" />;
  }

  return (
    <div style={{ marginTop: '1.5rem' }}>
      <h4 style={{ margin: '0 0 0.8rem', color: '#111827', fontSize: '1rem' }}>
        Replay History
      </h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
        {replay.map((v) => (
          <div
            key={`${v.seq}-${v.kind}`}
            style={{
              padding: '0.75rem 1rem',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              backgroundColor: '#f9fafb',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginBottom: '0.4rem',
                fontSize: '0.85rem',
              }}
            >
              <span style={{ fontWeight: 600, color: '#374151' }}>
                #{v.seq} — {v.kind}
              </span>
              <span style={{ color: '#6b7280', fontSize: '0.75rem' }}>
                By: {v.produced_by}
              </span>
            </div>
            <pre
              style={{
                margin: 0,
                padding: '0.5rem',
                backgroundColor: '#ffffff',
                border: '1px solid #e5e7eb',
                borderRadius: '4px',
                fontSize: '0.75rem',
                color: '#1f2937',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {JSON.stringify(v.payload, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
};
