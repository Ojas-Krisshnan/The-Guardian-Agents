// frontend/src/student/AttemptPage.tsx
import React, { useState } from 'react';
import type { ConceptNode, Test, SubmitAttemptResponse } from '../types/synapse';
import { NoteViewer } from './NoteViewer';
import {
  HelpCircle,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Award,
  Sparkles,
  ShieldCheck,
  FileText,
  Loader2,
  TrendingUp,
  AlertCircle,
} from 'lucide-react';

interface AttemptPageProps {
  concept: ConceptNode;
  test: Test;
  onSubmit: (testId: string, answers: Record<string, string>) => Promise<SubmitAttemptResponse>;
  onBack: () => void;
}

export const AttemptPage: React.FC<AttemptPageProps> = ({ concept, test, onSubmit, onBack }) => {
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<SubmitAttemptResponse | null>(null);
  const [showNoteDirectly, setShowNoteDirectly] = useState(false);

  const questions = test.questions || [];
  const answeredCount = Object.keys(selectedAnswers).length;
  const allAnswered = questions.length > 0 && questions.every((q) => selectedAnswers[q.id]);
  const progressPercent = questions.length > 0 ? Math.round((answeredCount / questions.length) * 100) : 0;

  const handleSelectOption = (questionId: string, option: string) => {
    setSelectedAnswers((prev) => ({ ...prev, [questionId]: option }));
  };

  const handleSubmit = async () => {
    if (!allAnswered || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const resp = await onSubmit(test.id, selectedAnswers);
      setResult(resp);
    } catch (err: any) {
      alert(`Submission error: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (showNoteDirectly && result?.note) {
    return (
      <NoteViewer
        conceptName={concept.name}
        notes={[result.note]}
        onClose={() => onBack()}
      />
    );
  }

  // If already submitted, display diagnostic evaluation
  if (result) {
    const masteryPct = Math.round(result.diagnosis.mastery_estimate * 100);
    const isPassing = masteryPct >= 70;

    return (
      <div className="glass-card" style={{ maxWidth: '820px', margin: '0 auto', padding: '2.5rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <div style={{
            width: '68px',
            height: '68px',
            borderRadius: '50%',
            background: isPassing ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
            color: isPassing ? 'var(--accent-emerald)' : 'var(--accent-amber)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1.25rem',
            border: `1px solid ${isPassing ? 'rgba(16, 185, 129, 0.35)' : 'rgba(245, 158, 11, 0.35)'}`,
            boxShadow: `0 0 24px ${isPassing ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)'}`,
          }}>
            <Award size={36} />
          </div>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.2rem 0.65rem',
            borderRadius: '9999px',
            background: 'rgba(56, 189, 248, 0.1)',
            color: 'var(--accent-cyan)',
            fontSize: '0.75rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            marginBottom: '0.5rem',
          }}>
            <Sparkles size={13} /> Assessment Evaluated
          </div>
          <h2 style={{ fontSize: '1.9rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
            Diagnostic Assessment Complete
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', maxWidth: '560px', margin: '0.4rem auto 0' }}>
            The AI diagnostic agent analyzed your response patterns and synthesized a personalized private study guide.
          </p>
        </div>

        {/* Score & Mastery Metric Cards */}
        <div className="grid-3" style={{ marginBottom: '2.25rem' }}>
          <div style={{
            background: 'rgba(13, 21, 39, 0.85)',
            padding: '1.25rem',
            borderRadius: 'var(--radius-md)',
            textAlign: 'center',
            border: '1px solid var(--border-subtle)',
          }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Raw Score
            </span>
            <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', marginTop: '0.35rem' }}>
              {result.attempt.score} <span style={{ fontSize: '1.1rem', color: 'var(--text-muted)', fontWeight: 600 }}>/ {result.attempt.total}</span>
            </div>
          </div>

          <div style={{
            background: 'rgba(13, 21, 39, 0.85)',
            padding: '1.25rem',
            borderRadius: 'var(--radius-md)',
            textAlign: 'center',
            border: '1px solid var(--border-subtle)',
          }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Estimated Mastery
            </span>
            <div style={{
              fontSize: '2rem',
              fontWeight: 800,
              color: isPassing ? 'var(--accent-emerald)' : 'var(--accent-amber)',
              marginTop: '0.35rem',
            }}>
              {masteryPct}%
            </div>
            <div style={{
              height: '4px',
              background: 'rgba(255, 255, 255, 0.08)',
              borderRadius: '2px',
              marginTop: '0.65rem',
              overflow: 'hidden',
            }}>
              <div style={{
                width: `${masteryPct}%`,
                height: '100%',
                background: isPassing ? 'var(--accent-emerald)' : 'var(--accent-amber)',
                borderRadius: '2px',
              }} />
            </div>
          </div>

          <div style={{
            background: 'rgba(13, 21, 39, 0.85)',
            padding: '1.25rem',
            borderRadius: 'var(--radius-md)',
            textAlign: 'center',
            border: '1px solid var(--border-subtle)',
          }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Trend Direction
            </span>
            <div style={{
              fontSize: '1.25rem',
              fontWeight: 700,
              color: 'var(--accent-cyan)',
              marginTop: '0.75rem',
              textTransform: 'capitalize',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.4rem',
            }}>
              <TrendingUp size={16} /> {result.diagnosis.trend.replace('_', ' ')}
            </div>
          </div>
        </div>

        {/* Breakdown of Question Classifications */}
        <div style={{ marginBottom: '2.5rem' }}>
          <h4 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertCircle size={18} color="var(--accent-cyan)" />
            Diagnostic Pattern Analysis
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {result.diagnosis.items.map((item, idx) => (
              <div
                key={idx}
                style={{
                  padding: '1.15rem',
                  background: 'rgba(13, 21, 39, 0.65)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.85rem',
                }}
              >
                <span className="badge badge-declining" style={{ textTransform: 'capitalize', whiteSpace: 'nowrap', marginTop: '0.1rem' }}>
                  {item.classification.replace('_', ' ')}
                </span>
                <p style={{ fontSize: '0.88rem', color: '#cbd5e1', lineHeight: 1.55 }}>
                  {item.reason}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Action Button to Tailored Note */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderTop: '1px solid var(--border-subtle)',
          paddingTop: '1.75rem',
          flexWrap: 'wrap',
          gap: '1rem',
        }}>
          <button className="btn btn-secondary" onClick={onBack}>
            <ArrowLeft size={16} /> Return to Concept Map
          </button>
          <button className="btn btn-primary" onClick={() => setShowNoteDirectly(true)}>
            <FileText size={16} /> Read Tailored Study Note <ArrowRight size={16} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '840px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Header & Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <button className="btn btn-secondary" onClick={onBack}>
          <ArrowLeft size={16} /> Back to Knowledge Map
        </button>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          color: 'var(--accent-cyan)',
          fontSize: '0.82rem',
          fontWeight: 700,
          background: 'rgba(56, 189, 248, 0.08)',
          border: '1px solid rgba(56, 189, 248, 0.25)',
          padding: '0.4rem 0.85rem',
          borderRadius: '9999px',
        }}>
          <HelpCircle size={15} /> Diagnostic Mode &bull; {concept.name}
        </div>
      </div>

      <div className="glass-card" style={{ padding: '2.25rem' }}>
        <div style={{ marginBottom: '1.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h2 style={{ fontSize: '1.65rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em', marginBottom: '0.35rem' }}>
                Diagnostic Assessment: {test.concept_name || concept.name}
              </h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                Select the answer reflecting your understanding. Mistake modes are automatically mapped into actionable study notes.
              </p>
            </div>
            <div style={{
              textAlign: 'right',
              minWidth: '120px',
            }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>Progress</span>
              <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--accent-cyan)' }}>
                {answeredCount} of {questions.length}
              </div>
            </div>
          </div>

          {/* Progress bar */}
          <div style={{
            height: '6px',
            background: 'rgba(255, 255, 255, 0.08)',
            borderRadius: '3px',
            marginTop: '1rem',
            overflow: 'hidden',
          }}>
            <div style={{
              width: `${progressPercent}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #0284c7, var(--accent-cyan))',
              borderRadius: '3px',
              transition: 'width 0.25s ease',
            }} />
          </div>
        </div>

        {/* Questions List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {questions.map((q, qIdx) => {
            const hasAnsweredThis = Boolean(selectedAnswers[q.id]);
            return (
              <div
                key={q.id}
                style={{
                  padding: '1.75rem',
                  background: 'rgba(13, 21, 39, 0.65)',
                  borderRadius: 'var(--radius-md)',
                  border: hasAnsweredThis ? '1px solid rgba(56, 189, 248, 0.3)' : '1px solid var(--border-subtle)',
                  transition: 'border-color 0.2s ease',
                }}
              >
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '0.75rem',
                }}>
                  <div style={{
                    fontSize: '0.75rem',
                    color: 'var(--accent-cyan)',
                    fontWeight: 800,
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                  }}>
                    Question {qIdx + 1} of {questions.length}
                  </div>
                  {hasAnsweredThis && (
                    <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '0.3rem', fontWeight: 600 }}>
                      <CheckCircle2 size={14} /> Answered
                    </span>
                  )}
                </div>

                <h3 style={{
                  fontSize: '1.15rem',
                  fontWeight: 700,
                  color: '#fff',
                  marginBottom: '1.25rem',
                  lineHeight: 1.5,
                }}>
                  {q.text}
                </h3>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {q.options.map((opt, optIdx) => {
                    const isSelected = selectedAnswers[q.id] === opt;
                    return (
                      <div
                        key={optIdx}
                        role="radio"
                        aria-checked={isSelected}
                        tabIndex={0}
                        onClick={() => handleSelectOption(q.id, opt)}
                        onKeyDown={(e) => {
                          if (e.key === ' ' || e.key === 'Enter') {
                            e.preventDefault();
                            handleSelectOption(q.id, opt);
                          }
                        }}
                        style={{
                          padding: '1rem 1.25rem',
                          borderRadius: 'var(--radius-sm)',
                          background: isSelected ? 'rgba(56, 189, 248, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                          border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                          color: isSelected ? '#fff' : '#cbd5e1',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.85rem',
                          transition: 'all 0.15s ease',
                          boxShadow: isSelected ? '0 0 16px rgba(56, 189, 248, 0.12)' : 'none',
                        }}
                      >
                        <div
                          style={{
                            width: '20px',
                            height: '20px',
                            borderRadius: '50%',
                            border: isSelected ? '6px solid var(--accent-cyan)' : '2px solid var(--text-muted)',
                            background: isSelected ? '#fff' : 'transparent',
                            flexShrink: 0,
                            transition: 'all 0.15s ease',
                          }}
                        />
                        <span style={{ fontSize: '0.92rem', flex: 1, lineHeight: 1.45 }}>{opt}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Submit Actions */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: '2.5rem',
          borderTop: '1px solid var(--border-subtle)',
          paddingTop: '1.5rem',
          flexWrap: 'wrap',
          gap: '1rem',
        }}>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            {answeredCount === questions.length ? (
              <span style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>All questions answered & ready for diagnosis</span>
            ) : (
              <span>Answer remaining {questions.length - answeredCount} question(s) to submit</span>
            )}
          </div>

          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={!allAnswered || isSubmitting}
            style={{ padding: '0.75rem 1.8rem', fontSize: '0.95rem' }}
          >
            {isSubmitting ? (
              <>
                <Loader2 size={18} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
                Submitting & Synthesizing...
              </>
            ) : (
              <>
                Complete Diagnostic Assessment <CheckCircle2 size={18} />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

