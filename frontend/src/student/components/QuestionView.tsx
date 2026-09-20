import React from 'react';
import { Question } from '../../shared/types';

interface QuestionViewProps {
  questions: Question[];
}

export const QuestionView: React.FC<QuestionViewProps> = ({ questions }) => {
  if (questions.length === 0) {
    return null;
  }

  return (
    <div
      style={{
        marginTop: '1rem',
        padding: '1rem',
        border: '1px solid #fef08a',
        backgroundColor: '#fefce8',
        borderRadius: '8px',
      }}
    >
      <div style={{ fontWeight: 600, color: '#854d0e', marginBottom: '0.5rem' }}>
        Waiting for expert response
      </div>
      {questions.map((q) => (
        <div
          key={q.id}
          style={{
            padding: '0.75rem',
            backgroundColor: '#ffffff',
            border: '1px solid #fef08a',
            borderRadius: '6px',
            marginTop: '0.5rem',
          }}
        >
          <div style={{ fontWeight: 500, color: '#111827', fontSize: '0.9rem' }}>
            {q.question}
          </div>
          <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.3rem' }}>
            Question ID: {q.id}
          </div>
        </div>
      ))}
    </div>
  );
};
