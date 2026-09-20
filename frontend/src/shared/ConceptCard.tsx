// frontend/src/shared/ConceptCard.tsx
import React from 'react';
import type { ConceptNode } from '../types/synapse';
import { BookOpen, CheckCircle2, ArrowRight, Layers, FileText, BarChart3, Tag } from 'lucide-react';

interface ConceptCardProps {
  concept: ConceptNode;
  userRole: 'teacher' | 'student';
  hasNotes?: boolean;
  onTakeTest?: (concept: ConceptNode) => void;
  onViewNotes?: (concept: ConceptNode) => void;
  onViewAnalytics?: (concept: ConceptNode) => void;
}

export const ConceptCard: React.FC<ConceptCardProps> = ({
  concept,
  userRole,
  hasNotes = false,
  onTakeTest,
  onViewNotes,
  onViewAnalytics,
}) => {
  const category = (concept as any).category as string | undefined;

  const getCategoryTheme = (cat?: string) => {
    switch (cat) {
      case 'foundations':
        return { color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.12)', border: 'rgba(56, 189, 248, 0.3)' };
      case 'algorithms':
        return { color: '#818cf8', bg: 'rgba(129, 140, 248, 0.12)', border: 'rgba(129, 140, 248, 0.3)' };
      case 'deep_learning':
        return { color: '#34d399', bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.3)' };
      case 'cognitive_agents':
        return { color: '#c084fc', bg: 'rgba(192, 132, 252, 0.12)', border: 'rgba(192, 132, 252, 0.3)' };
      default:
        return { color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.12)', border: 'rgba(56, 189, 248, 0.3)' };
    }
  };

  const theme = getCategoryTheme(category);

  return (
    <div className="glass-card glass-card-interactive" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Category Pill & Notes Status */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
        {category ? (
          <span style={{
            fontSize: '0.7rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: theme.color,
            background: theme.bg,
            border: `1px solid ${theme.border}`,
            padding: '0.15rem 0.55rem',
            borderRadius: '9999px',
          }}>
            {category.replace('_', ' ')}
          </span>
        ) : (
          <span style={{
            fontSize: '0.7rem',
            fontWeight: 600,
            color: 'var(--text-muted)',
            textTransform: 'uppercase',
          }}>
            Concept Node
          </span>
        )}

        {hasNotes && (
          <span className="badge badge-improving" style={{ fontSize: '0.72rem' }}>
            <CheckCircle2 size={12} /> Notes Ready
          </span>
        )}
      </div>

      <div className="card-header" style={{ marginBottom: '0.65rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div style={{
            background: theme.bg,
            color: theme.color,
            padding: '0.5rem',
            borderRadius: 'var(--radius-sm)',
            display: 'flex',
            border: `1px solid ${theme.border}`,
            flexShrink: 0,
          }}>
            <BookOpen size={18} />
          </div>
          <h3 style={{ fontSize: '1.12rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.01em', lineHeight: 1.3 }}>
            {concept.name}
          </h3>
        </div>
      </div>

      <p style={{
        color: 'var(--text-secondary)',
        fontSize: '0.88rem',
        marginBottom: '1.25rem',
        flex: 1,
        lineHeight: 1.55,
      }}>
        {concept.summary || 'Essential domain concept with verified cognitive assessment metrics.'}
      </p>

      {concept.prerequisites && concept.prerequisites.length > 0 && (
        <div style={{ marginBottom: '1.25rem' }}>
          <div style={{
            fontSize: '0.7rem',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: 'var(--text-muted)',
            marginBottom: '0.45rem',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
          }}>
            <Layers size={12} /> Prerequisites ({concept.prerequisites.length})
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
            {concept.prerequisites.map((prereq, idx) => (
              <span
                key={idx}
                style={{
                  background: 'rgba(255, 255, 255, 0.04)',
                  color: 'var(--accent-cyan)',
                  padding: '0.2rem 0.55rem',
                  borderRadius: '4px',
                  fontSize: '0.75rem',
                  fontFamily: 'var(--font-mono)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                {prereq}
              </span>
            ))}
          </div>
        </div>
      )}

      <div style={{
        display: 'flex',
        gap: '0.5rem',
        marginTop: 'auto',
        borderTop: '1px solid var(--border-subtle)',
        paddingTop: '1.15rem',
      }}>
        {userRole === 'teacher' ? (
          <button
            type="button"
            className="btn btn-primary"
            style={{ width: '100%', fontSize: '0.85rem' }}
            onClick={() => onViewAnalytics?.(concept)}
          >
            <BarChart3 size={15} /> Class Analytics <ArrowRight size={14} />
          </button>
        ) : (
          <>
            <button
              type="button"
              className="btn btn-primary"
              style={{ flex: 1, fontSize: '0.85rem' }}
              onClick={() => onTakeTest?.(concept)}
            >
              Take Test <ArrowRight size={14} />
            </button>
            {hasNotes && (
              <button
                type="button"
                className="btn btn-secondary"
                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}
                onClick={() => onViewNotes?.(concept)}
                title="View Tailored Private Notes"
              >
                <FileText size={15} /> Notes
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
};

