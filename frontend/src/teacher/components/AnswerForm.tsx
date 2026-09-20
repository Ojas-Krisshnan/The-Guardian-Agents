import React, { useState } from 'react';
import { Question } from '../../shared/types';
import { ErrorMessage } from '../../shared/ui/ErrorMessage';

interface AnswerFormProps {
  question: Question;
  onAnswerSubmit: (questionId: string, answer: string) => Promise<void>;
  answering: boolean;
}

export const AnswerForm: React.FC<AnswerFormProps> = ({
  question,
  onAnswerSubmit,
  answering,
}) => {
  const [answerText, setAnswerText] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!answerText.trim()) {
      setValidationError('Please enter an answer before submitting.');
      return;
    }
    setValidationError(null);
    await onAnswerSubmit(question.id, answerText.trim());
    setAnswerText('');
  };

  return (
    <div
      style={{
        padding: '1rem',
        border: '1px solid #fde68a',
        backgroundColor: '#fffbeb',
        borderRadius: '8px',
        marginTop: '0.8rem',
      }}
    >
      <div style={{ fontWeight: 600, color: '#92400e', marginBottom: '0.4rem', fontSize: '0.95rem' }}>
        Pending Expert Question ({question.id})
      </div>
      <p style={{ margin: '0 0 0.8rem', color: '#1f2937', fontSize: '0.9rem' }}>
        <strong>Question:</strong> {question.question}
      </p>

      {validationError && <ErrorMessage message={validationError} />}

      <form onSubmit={handleSubmit}>
        <textarea
          value={answerText}
          onChange={(e) => setAnswerText(e.target.value)}
          placeholder="Type expert guidance/answer..."
          rows={3}
          style={{
            width: '100%',
            padding: '0.6rem',
            borderRadius: '6px',
            border: '1px solid #d1d5db',
            boxSizing: 'border-box',
            fontFamily: 'inherit',
            fontSize: '0.85rem',
            marginBottom: '0.6rem',
          }}
        />
        <button
          type="submit"
          disabled={answering}
          style={{
            padding: '0.5rem 1rem',
            backgroundColor: '#d97706',
            color: '#ffffff',
            border: 'none',
            borderRadius: '6px',
            fontWeight: 600,
            cursor: answering ? 'not-allowed' : 'pointer',
          }}
        >
          {answering ? 'Submitting Answer...' : 'Answer Question'}
        </button>
      </form>
    </div>
  );
};
