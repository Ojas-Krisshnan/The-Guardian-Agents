import React from 'react';

export const EmptyState: React.FC<{ message: string }> = ({ message }) => {
  return (
    <div
      style={{
        padding: '2rem 1rem',
        textAlign: 'center',
        color: '#9ca3af',
        border: '1px dashed #e5e7eb',
        borderRadius: '8px',
      }}
    >
      {message}
    </div>
  );
};
