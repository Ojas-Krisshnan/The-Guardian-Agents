import React from 'react';

export const ErrorMessage: React.FC<{ message: string }> = ({ message }) => {
  return (
    <div
      style={{
        padding: '0.75rem 1rem',
        margin: '0.5rem 0',
        backgroundColor: '#fee2e2',
        border: '1px solid #fca5a5',
        borderRadius: '6px',
        color: '#991b1b',
        fontSize: '0.9rem',
      }}
    >
      {message}
    </div>
  );
};
