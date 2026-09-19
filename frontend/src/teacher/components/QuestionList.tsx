import React from 'react';
import { Question } from '../../shared/types';
import { AnswerForm } from './AnswerForm';
import { EmptyState } from '../../shared/ui/EmptyState';

interface QuestionListProps {
  questions: Question[];
  onAnswerSubmit: (questionId: string, answer: string) => Promise<void>;
  answering: boolean;
}

export const QuestionList: React.FC<QuestionListProps> = ({
  questions,
  onAnswerSubmit,
  answering,
}) => {
  if (questions.length === 0) {
    return <EmptyState message="No expert questions for this run" />;
  }

  const pendingQuestions = questions.filter((q) => !q.is_answered);
  const answeredQuestions = questions.filter((q) => q.is_answered);

  return (
    <div style={{ marginTop: '1.5rem' }}>
      <h4 style={{ margin: '0 0 0.8rem', color: '#111827', fontSize: '1rem' }}>
        Expert Questions ({questions.length})
      </h4>

      {pendingQuestions.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          {pendingQuestions.map((q) => (
            <AnswerForm
              key={q.id}
              question={q}
              onAnswerSubmit={onAnswerSubmit}
              answering={answering}
            />
          ))}
        </div>
      )}

      {answeredQuestions.length > 0 && (
        <div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#065f46', marginBottom: '0.4rem' }}>
            Answered Questions ({answeredQuestions.length})
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {answeredQuestions.map((q) => (
              <div
                key={q.id}
                style={{
                  padding: '0.75rem',
                  border: '1px solid #a7f3d0',
                  borderRadius: '6px',
                  backgroundColor: '#ecfdf5',
                }}
              >
                <div style={{ fontWeight: 500, color: '#111827', fontSize: '0.85rem' }}>
                  <strong>Q:</strong> {q.question}
                </div>
                <div style={{ fontSize: '0.85rem', color: '#065f46', marginTop: '0.3rem' }}>
                  <strong>Answer:</strong> {q.answer}
                </div>
                <span
                  style={{
                    display: 'inline-block',
                    marginTop: '0.3rem',
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    color: '#047857',
                    backgroundColor: '#d1fae5',
                    padding: '0.15rem 0.4rem',
                    borderRadius: '4px',
                  }}
                >
                  STATUS: ANSWERED
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
