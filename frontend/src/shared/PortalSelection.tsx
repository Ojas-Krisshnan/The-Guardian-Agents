// frontend/src/shared/PortalSelection.tsx
import React, { useState } from 'react';
import {
  BrainCircuit,
  GraduationCap,
  Layers,
  ArrowRight,
  ShieldCheck,
  Activity,
  BarChart3,
  BookOpen,
  CheckCircle2,
} from 'lucide-react';
import type { PortalRole } from '../App';

interface PortalSelectionProps {
  onSelectPortal: (portal: PortalRole) => void;
}

export const PortalSelection: React.FC<PortalSelectionProps> = ({ onSelectPortal }) => {
  const [selected, setSelected] = useState<PortalRole | null>(null);

  const handleSelect = (portal: PortalRole) => {
    setSelected(portal);
    // Subtle, clean tactile feedback before workspace activation
    setTimeout(() => {
      onSelectPortal(portal);
    }, 120);
  };

  return (
    <div
      className="portal-selection-container"
      role="region"
      aria-label="Synapse Workspace Selection"
    >
      <div className="portal-selection-content">
        {/* Header Section */}
        <div className="portal-selection-header">
          <div className="portal-selection-brand-badge">
            <BrainCircuit size={18} className="portal-brand-circuit" />
            <span className="portal-brand-text">SYNAPSE</span>
          </div>

          <h1 className="portal-selection-title">Choose your workspace</h1>
          <p className="portal-selection-subtitle">
            Select where you want to go. You can switch between learner and faculty workspaces at any time.
          </p>
        </div>

        {/* Portal Choices Grid */}
        <div className="portal-cards-grid" role="list">
          {/* Card 1: Student Portal */}
          <div
            role="button"
            tabIndex={0}
            aria-label="Enter Student Portal: Learn, take assessments, review mistakes, and track conceptual mastery"
            className={`portal-card portal-card-student ${selected === 'student' ? 'selected' : ''}`}
            onClick={() => handleSelect('student')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleSelect('student');
              }
            }}
          >
            <div className="portal-card-top">
              <div className="portal-card-icon-wrapper student-icon-wrapper">
                <Layers size={24} className="portal-card-icon" />
              </div>
              <span className="portal-card-pill student-pill">
                Learner
              </span>
            </div>

            <div className="portal-card-body">
              <h2 className="portal-card-title">Student Portal</h2>
              <p className="portal-card-desc">
                Learn, test, review &amp; track conceptual mastery through diagnostic assessments and private revision notes.
              </p>

              <div className="portal-card-features">
                <div className="portal-feature-item">
                  <BookOpen size={15} className="feature-icon" />
                  <span>Curriculum concept graph &amp; study notes</span>
                </div>
                <div className="portal-feature-item">
                  <ShieldCheck size={15} className="feature-icon" />
                  <span>Adaptive tests &amp; AI mistake diagnosis</span>
                </div>
                <div className="portal-feature-item">
                  <Activity size={15} className="feature-icon" />
                  <span>Personal mastery analytics &amp; trend tracking</span>
                </div>
              </div>
            </div>

            <div className="portal-card-footer">
              <button
                type="button"
                className="portal-cta-btn student-cta"
                tabIndex={-1}
                aria-hidden="true"
              >
                <span>Enter Student Portal</span>
                <ArrowRight size={16} className="cta-arrow" />
              </button>
            </div>
          </div>

          {/* Card 2: Teacher Portal */}
          <div
            role="button"
            tabIndex={0}
            aria-label="Enter Teacher Portal: Teach, author curriculum, analyze cohorts, and review insights"
            className={`portal-card portal-card-teacher ${selected === 'teacher' ? 'selected' : ''}`}
            onClick={() => handleSelect('teacher')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleSelect('teacher');
              }
            }}
          >
            <div className="portal-card-top">
              <div className="portal-card-icon-wrapper teacher-icon-wrapper">
                <GraduationCap size={24} className="portal-card-icon" />
              </div>
              <span className="portal-card-pill teacher-pill">
                Faculty
              </span>
            </div>

            <div className="portal-card-body">
              <h2 className="portal-card-title">Teacher Portal</h2>
              <p className="portal-card-desc">
                Teach, analyze &amp; manage classrooms, author assessments, and inspect data-grounded AI pedagogical recommendations.
              </p>

              <div className="portal-card-features">
                <div className="portal-feature-item">
                  <BarChart3 size={15} className="feature-icon" />
                  <span>Classroom score distributions &amp; analytics</span>
                </div>
                <div className="portal-feature-item">
                  <CheckCircle2 size={15} className="feature-icon" />
                  <span>Assessment creator &amp; question sets</span>
                </div>
                <div className="portal-feature-item">
                  <Activity size={15} className="feature-icon" />
                  <span>AI teaching insights &amp; concept weaknesses</span>
                </div>
              </div>
            </div>

            <div className="portal-card-footer">
              <button
                type="button"
                className="portal-cta-btn teacher-cta"
                tabIndex={-1}
                aria-hidden="true"
              >
                <span>Enter Teacher Portal</span>
                <ArrowRight size={16} className="cta-arrow" />
              </button>
            </div>
          </div>
        </div>

        {/* Minimal Footnote */}
        <div className="portal-selection-foot-note">
          <span>Synapse Educational Architecture &bull; Zero-Knowledge Privacy &bull; SQLite Spine</span>
        </div>
      </div>
    </div>
  );
};
