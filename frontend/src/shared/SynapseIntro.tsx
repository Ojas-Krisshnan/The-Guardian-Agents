// frontend/src/shared/SynapseIntro.tsx
import React, { useEffect, useCallback } from 'react';
import { BrainCircuit, ArrowRight } from 'lucide-react';

interface SynapseIntroProps {
  onComplete: () => void;
}

export const SynapseIntro: React.FC<SynapseIntroProps> = ({ onComplete }) => {
  const handleProceed = useCallback(() => {
    onComplete();
  }, [onComplete]);

  // Keyboard accessibility: Enter or Space activates Get Started
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handleProceed();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleProceed]);

  return (
    <div
      className="title-page-container"
      role="region"
      aria-label="Synapse Welcome Page"
    >
      <div className="title-page-content">
        {/* Simple Brand Badge */}
        <div className="title-brand-badge">
          <BrainCircuit size={20} className="title-brand-icon" />
          <span className="title-brand-name">SYNAPSE</span>
        </div>

        {/* Clean, Human-Designed Headline */}
        <h1 className="title-main-heading">
          SYNAPSE
        </h1>

        {/* Quiet, Human Subtitle */}
        <p className="title-subheading">
          Your learning space
        </p>

        {/* Focused Call to Action */}
        <div className="title-action-wrapper">
          <button
            type="button"
            className="title-get-started-btn"
            onClick={handleProceed}
            autoFocus
            aria-label="Get Started and choose your workspace"
          >
            <span>Get Started</span>
            <ArrowRight size={18} className="btn-arrow" />
          </button>
        </div>

        {/* Minimal Educational Footer Note */}
        <p className="title-micro-note">
          Autonomous diagnostic learning &amp; concept mastery
        </p>
      </div>
    </div>
  );
};
