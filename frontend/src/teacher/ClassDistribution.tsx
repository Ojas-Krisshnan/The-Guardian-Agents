// frontend/src/teacher/ClassDistribution.tsx
import React from 'react';
import type { ClassAnalytics } from '../types/synapse';
import { Users, AlertTriangle, TrendingUp, TrendingDown, Minus, Clock, Award, ShieldAlert } from 'lucide-react';

interface ClassDistributionProps {
  analytics: ClassAnalytics;
}

export const ClassDistribution: React.FC<ClassDistributionProps> = ({ analytics }) => {
  const masteryPercent = Math.round(analytics.average_mastery * 100);
  const isHighMastery = masteryPercent >= 70;
  const trends = analytics.trend_distribution || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Overview Stat Cards */}
      <div className="grid-3">
        <div className="glass-card" style={{ padding: '1.25rem', background: 'rgba(13, 21, 39, 0.75)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Class Size
            </span>
            <Users size={18} color="var(--accent-cyan)" />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', lineHeight: 1.15 }}>
            {analytics.student_count}
          </div>
          <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>Assessed Learners in Cohort</span>
        </div>

        <div className="glass-card" style={{ padding: '1.25rem', background: 'rgba(13, 21, 39, 0.75)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Mean Mastery
            </span>
            <Award size={18} color={isHighMastery ? 'var(--accent-emerald)' : 'var(--accent-amber)'} />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: isHighMastery ? '#34d399' : '#fbbf24', lineHeight: 1.15 }}>
            {masteryPercent}%
          </div>
          <div style={{
            height: '5px',
            background: 'rgba(255, 255, 255, 0.08)',
            borderRadius: '3px',
            marginTop: '0.65rem',
            overflow: 'hidden',
          }}>
            <div style={{
              width: `${masteryPercent}%`,
              height: '100%',
              background: isHighMastery ? 'linear-gradient(90deg, #059669, #10b981)' : 'linear-gradient(90deg, #d97706, #f59e0b)',
              borderRadius: '3px',
              transition: 'width 0.4s ease',
            }} />
          </div>
        </div>

        <div className="glass-card" style={{ padding: '1.25rem', background: 'rgba(13, 21, 39, 0.75)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Needs Support
            </span>
            <AlertTriangle size={18} color="var(--accent-rose)" />
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--accent-rose)', lineHeight: 1.15 }}>
            {analytics.weak_students?.length || 0}
          </div>
          <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>Below 0.50 Mastery Invariant</span>
        </div>
      </div>

      {/* Weak Students Alert Section */}
      {analytics.weak_students && analytics.weak_students.length > 0 && (
        <div className="glass-card" style={{
          borderLeft: '4px solid var(--accent-rose)',
          background: 'rgba(244, 63, 94, 0.06)',
          padding: '1.25rem 1.5rem',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.65rem' }}>
            <ShieldAlert size={18} color="var(--accent-rose)" />
            <h4 style={{ fontSize: '0.98rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Learners Requiring Direct Targeted Remediation
            </h4>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.85rem', lineHeight: 1.5 }}>
            The following students exhibit verified conceptual blind spots and scores below the 0.50 threshold:
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {analytics.weak_students.map((stId, idx) => (
              <span key={idx} className="badge badge-weak" style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', padding: '0.25rem 0.65rem' }}>
                {stId}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Trend Distribution */}
      <div className="glass-card" style={{ background: 'rgba(13, 21, 39, 0.75)' }}>
        <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
          Cohort Cycle Trajectories
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '1rem' }}>
          <div style={{ background: 'rgba(16, 185, 129, 0.08)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(16, 185, 129, 0.22)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#34d399', fontSize: '0.78rem', fontWeight: 700 }}>
              <TrendingUp size={14} /> Improving
            </div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.35rem', color: '#fff' }}>
              {trends.improving || 0}
            </div>
          </div>

          <div style={{ background: 'rgba(56, 189, 248, 0.08)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(56, 189, 248, 0.22)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#38bdf8', fontSize: '0.78rem', fontWeight: 700 }}>
              <Minus size={14} /> Stable
            </div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.35rem', color: '#fff' }}>
              {trends.stable || 0}
            </div>
          </div>

          <div style={{ background: 'rgba(244, 63, 94, 0.08)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(244, 63, 94, 0.22)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#fb7185', fontSize: '0.78rem', fontWeight: 700 }}>
              <TrendingDown size={14} /> Declining
            </div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.35rem', color: '#fff' }}>
              {trends.declining || 0}
            </div>
          </div>

          <div style={{ background: 'rgba(245, 158, 11, 0.08)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(245, 158, 11, 0.22)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#fbbf24', fontSize: '0.78rem', fontWeight: 700 }}>
              <Clock size={14} /> Initial Cycle
            </div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.35rem', color: '#fff' }}>
              {trends.new || 0}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

