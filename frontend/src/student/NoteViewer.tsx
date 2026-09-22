// frontend/src/student/NoteViewer.tsx
import React, { useState } from 'react';
import type { NoteVersion } from '../types/synapse';
import { ShieldCheck, History, X, Sparkles, CheckCircle2, Copy, Check, FileText } from 'lucide-react';

interface NoteViewerProps {
  conceptName: string;
  notes: NoteVersion[];
  onClose?: () => void;
}

export const NoteViewer: React.FC<NoteViewerProps> = ({ conceptName, notes, onClose }) => {
  const [selectedVersionIdx, setSelectedVersionIdx] = useState<number>(notes.length - 1);
  const [copied, setCopied] = useState(false);
  const currentNote = notes[selectedVersionIdx] || notes[0];

  if (!currentNote) {
    return (
      <div className="glass-card" style={{ padding: '2.5rem', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-secondary)' }}>No private notes available yet. Complete a test attempt to generate one!</p>
      </div>
    );
  }

  const handleCopy = () => {
    if (!currentNote?.markdown) return;
    navigator.clipboard.writeText(currentNote.markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Enhanced inline text renderer for bold, code, and [[wiki-links]]
  const renderInline = (text: string): React.ReactNode => {
    // Regex for [[concept]], `code`, **bold**
    const parts = text.split(/(\[\[.*?\]\]|`.*?`|\*\*.*?\*\*)/g);
    return parts.map((part, pIdx) => {
      if (part.startsWith('[[') && part.endsWith(']]')) {
        const title = part.slice(2, -2);
        return (
          <span
            key={pIdx}
            style={{
              color: 'var(--accent-cyan)',
              background: 'rgba(56, 189, 248, 0.12)',
              padding: '0.1rem 0.4rem',
              borderRadius: '4px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.85em',
              fontWeight: 600,
              border: '1px solid rgba(56, 189, 248, 0.25)',
            }}
          >
            {title}
          </span>
        );
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code
            key={pIdx}
            style={{
              background: 'rgba(255, 255, 255, 0.08)',
              padding: '0.1rem 0.35rem',
              borderRadius: '4px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.88em',
              color: '#f8fafc',
            }}
          >
            {part.slice(1, -1)}
          </code>
        );
      }
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={pIdx} style={{ color: '#fff' }}>{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  // Lightweight Markdown parser for headers, lists, and tables
  const renderMarkdown = (md: string) => {
    const lines = md.split('\n');
    const elements: React.ReactNode[] = [];
    let inTable = false;
    let tableRows: string[][] = [];

    const flushTable = (key: number) => {
      if (tableRows.length === 0) return null;
      const headers = tableRows[0];
      const rows = tableRows.slice(2); // skip separator row |---|---|
      const tableEl = (
        <div key={`table-${key}`} style={{ overflowX: 'auto', margin: '1.25rem 0' }}>
          <table>
            <thead>
              <tr>
                {headers.map((h, i) => (
                  <th key={i}>{h.trim()}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rIdx) => (
                <tr key={rIdx}>
                  {row.map((cell, cIdx) => (
                    <td key={cIdx}>{renderInline(cell.trim())}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
      inTable = false;
      return tableEl;
    };

    lines.forEach((line, idx) => {
      const trimmed = line.trim();

      if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
        inTable = true;
        const cells = trimmed
          .slice(1, -1)
          .split('|')
          .map((c) => c.trim());
        tableRows.push(cells);
        return;
      } else if (inTable) {
        const table = flushTable(idx);
        if (table) elements.push(table);
      }

      if (trimmed.startsWith('# ')) {
        elements.push(
          <h2 key={idx} style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', margin: '1.25rem 0 0.75rem', letterSpacing: '-0.02em' }}>
            {trimmed.slice(2)}
          </h2>
        );
      } else if (trimmed.startsWith('## ')) {
        elements.push(
          <h3 key={idx} style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-cyan)', margin: '1.25rem 0 0.6rem', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <Sparkles size={16} /> {trimmed.slice(3)}
          </h3>
        );
      } else if (trimmed.startsWith('- ')) {
        elements.push(
          <li key={idx} style={{ marginLeft: '1.5rem', marginBottom: '0.45rem', color: '#cbd5e1' }}>
            {renderInline(trimmed.slice(2))}
          </li>
        );
      } else if (trimmed.length > 0) {
        elements.push(
          <p key={idx} style={{ marginBottom: '0.85rem', color: '#cbd5e1', lineHeight: 1.65 }}>
            {renderInline(trimmed)}
          </p>
        );
      }
    });

    if (inTable) {
      const table = flushTable(lines.length);
      if (table) elements.push(table);
    }

    return elements;
  };

  return (
    <div className="glass-card" style={{ maxWidth: '880px', width: '100%', margin: '0 auto', padding: '2.25rem', boxShadow: '0 20px 45px rgba(0, 0, 0, 0.7)' }}>
      {/* Privacy Guarantee Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'rgba(16, 185, 129, 0.08)',
        border: '1px solid rgba(16, 185, 129, 0.28)',
        borderRadius: 'var(--radius-sm)',
        padding: '0.65rem 1.15rem',
        marginBottom: '1.5rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', color: '#34d399', fontSize: '0.82rem', fontWeight: 600 }}>
          <ShieldCheck size={18} />
          Student Private Study Note &bull; Enforced by Cryptographic Token Isolation (Teacher Access Blocked)
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '0.2rem',
              display: 'flex',
            }}
            aria-label="Close Note Viewer"
          >
            <X size={18} />
          </button>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
        <div>
          <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--accent-cyan)', fontWeight: 700 }}>
            Personalized Diagnostic Synthesis
          </span>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
            {conceptName}
          </h2>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          {/* Version Switcher */}
          {notes.length > 1 && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              background: 'rgba(13, 21, 39, 0.85)',
              padding: '0.3rem',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
            }}>
              <History size={14} color="var(--text-muted)" style={{ marginLeft: '0.3rem' }} />
              {notes.map((note, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setSelectedVersionIdx(idx)}
                  style={{
                    padding: '0.25rem 0.6rem',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    borderRadius: '4px',
                    border: 'none',
                    background: idx === selectedVersionIdx ? 'var(--accent-cyan)' : 'transparent',
                    color: idx === selectedVersionIdx ? '#080c15' : 'var(--text-secondary)',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  v{note.version}
                </button>
              ))}
            </div>
          )}

          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleCopy}
            style={{ padding: '0.45rem 0.85rem', fontSize: '0.78rem' }}
          >
            {copied ? <><Check size={14} color="var(--accent-emerald)" /> Copied</> : <><Copy size={14} /> Copy Note</>}
          </button>
        </div>
      </div>

      <div className="markdown-body" style={{
        background: 'rgba(13, 21, 39, 0.6)',
        padding: '1.75rem',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-subtle)',
      }}>
        {renderMarkdown(currentNote.markdown)}
      </div>

      <div style={{ marginTop: '1.75rem', display: 'flex', justifyContent: 'flex-end' }}>
        {onClose && (
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Back to Dashboard
          </button>
        )}
      </div>
    </div>
  );
};

