import React from 'react';

export const Loading: React.FC<{ message?: string }> = ({ message = 'Loading...' }) => {
  return (
    <div style={{ padding: '1rem', textAlign: 'center', color: '#6b7280' }}>
      <span>{message}</span>
    </div>
  );
};
