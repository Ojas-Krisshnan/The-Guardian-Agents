// frontend/src/teacher/MasteryTrendChart.tsx
import React from 'react';
import type { AnalysisPayload, TrendLabel } from '../types/synapse';
import { TrendingUp, TrendingDown, Minus, Clock, AlertCircle, History } from 'lucide-react';

interface MasteryTrendChartProps {
  trends: AnalysisPayload[];
}

export const MasteryTrendChart: React.FC<MasteryTrendChartProps> = ({ trends }) => {
  if (!trends || trends.length === 0) {
    return (
      <div className="glass-card" style={{ textAlign: 'center', padding: '3rem 2rem', color: 'var(--text-secondary)' }}>
        <History size={32} color="var(--text-muted)" style={{ margin: '0 auto 0.75rem' }} />
        <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>No Historical Trajectories</div>
        <div style={{ fontSize: '0.85rem' }}>Diagnostic assessment cycles for this concept will appear here as students complete tests.</div>
      </div>
    );
  }

  const getTrendBadge = (trend: TrendLabel) => {
    switch (trend) {
      case 'improving':
        return <span className="badge badge-improving"><TrendingUp size={12} /> Improving</span>;
      case 'declining':
        return <span className="badge badge-declining"><TrendingDown size={12} /> Declining</span>;
      case 'stable':
        return <span className="badge badge-stable"><Minus size={12} /> Stable</span>;
      case 'still_weak':
        return <span className="badge badge-weak"><AlertCircle size={12} /> Still Weak</span>;
      default:
        return <span className="badge badge-new"><Clock size={12} /> Initial</span>;
    }
  };

  return (
    <div className="glass-card" style={{ background: 'rgba(13, 21, 39, 0.75)' }}>
      <div className="card-header" style={{ marginBottom: '1.25rem' }}>
        <div>
          <h4 className="card-title" style={{ fontSize: '1.05rem', fontWeight: 800, letterSpacing: '-0.01em' }}>
            Student Cognitive Trajectory Log
          </h4>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Real-time mastery updates across active diagnostic cycles
          </span>
        </div>
        <span className="badge badge-stable" style={{ fontSize: '0.72rem' }}>
          {trends.length} Cycle Records
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {trends.map((item, idx) => {
          const pct = Math.round(item.mastery_estimate * 100);
          const isHigh = pct >= 70;
          const isMedium = pct >= 50 && pct < 70;

          return (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.85rem 1.15rem',
                background: 'rgba(15, 23, 42, 0.65)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                transition: 'border-color 0.15s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', minWidth: '160px' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                  {item.student_id}
                </span>
                <span style={{
                  fontSize: '0.72rem',
                  color: 'var(--text-secondary)',
                  background: 'rgba(255, 255, 255, 0.05)',
                  padding: '0.15rem 0.5rem',
                  borderRadius: '4px',
                  fontWeight: 600,
                }}>
                  Cycle {item.cycle_number}
                </span>
              </div>

              {/* Progress bar */}
              <div style={{ flex: 1, margin: '0 1.5rem', maxWidth: '280px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '0.3rem' }}>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Mastery Index</span>
                  <span style={{ fontWeight: 800, color: isHigh ? '#34d399' : isMedium ? '#38bdf8' : '#f43f5e' }}>{pct}%</span>
                </div>
                <div style={{ height: '6px', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div
                    style={{
                      width: `${pct}%`,
                      height: '100%',
                      background: isHigh
                        ? 'linear-gradient(90deg, #059669, #10b981)'
                        : isMedium
                        ? 'linear-gradient(90deg, #0284c7, #38bdf8)'
                        : 'linear-gradient(90deg, #e11d48, #f43f5e)',
                      borderRadius: '3px',
                      transition: 'width 0.3s ease',
                    }}
                  />
                </div>
              </div>

              <div>{getTrendBadge(item.trend)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

