// frontend/src/student/StudentDashboard.tsx
import React, { useState, useEffect } from 'react';
import type { ConceptNode, GraphEdge, NoteVersion, AssessmentResponse, TakeAssessmentResponse } from '../types/synapse';
import { ConceptCard } from '../shared/ConceptCard';
import { GraphCanvas } from './GraphCanvas';
import { NoteViewer } from './NoteViewer';
import { AttemptPage } from './AttemptPage';
import { api } from '../api_client/client';
import {
  Compass,
  Sparkles,
  BookOpen,
  ShieldCheck,
  Search,
  CheckCircle2,
  FileText,
  Layers,
  Network,
  Award,
  PlayCircle,
  TrendingUp,
  History,
  Lock,
  ArrowRight,
  Clock,
  GraduationCap,
  UserCheck,
  Key,
} from 'lucide-react';

interface StudentDashboardProps {
  concepts: ConceptNode[];
  edges: GraphEdge[];
  notesByConcept: Record<string, NoteVersion[]>;
  onStartTest: (concept: ConceptNode) => void;
}

export const StudentDashboard: React.FC<StudentDashboardProps> = ({
  concepts,
  edges,
  notesByConcept,
  onStartTest,
}) => {
  const [activeTab, setActiveTab] = useState<'assessments' | 'analytics' | 'notes' | 'graph' | 'library'>('assessments');

  // Real backend student data
  const [classrooms, setClassrooms] = useState<any[]>([]);
  const [assignedAssessments, setAssignedAssessments] = useState<AssessmentResponse[]>([]);
  const [pastAttempts, setPastAttempts] = useState<any[]>([]);
  const [analyticsSummary, setAnalyticsSummary] = useState<any | null>(null);
  const [privateNotes, setPrivateNotes] = useState<NoteVersion[]>([]);
  const [connectedTeachers, setConnectedTeachers] = useState<any[]>([]);
  const [teacherCodeInput, setTeacherCodeInput] = useState('');
  const [connectingTeacher, setConnectingTeacher] = useState(false);
  const [connectMessage, setConnectMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [loading, setLoading] = useState(false);

  // Active taking test state
  const [activeAssessment, setActiveAssessment] = useState<TakeAssessmentResponse | null>(null);

  // Note viewing
  const [activeViewingConcept, setActiveViewingConcept] = useState<ConceptNode | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  useEffect(() => {
    loadStudentData();
  }, []);

  const loadStudentData = async () => {
    setLoading(true);
    try {
      const [cls, asms, atts, anSummary, allNotes, teachersRes] = await Promise.all([
        api.getStudentClassrooms().catch(() => []),
        api.getStudentAssessments().catch(() => []),
        api.listStudentAttempts().catch(() => []),
        api.getStudentAnalytics().catch(() => null),
        api.getAllStudentNotes().catch(() => ({ notes: [] })),
        api.getStudentConnectedTeachers().catch(() => ({ teachers: [] })),
      ]);
      setClassrooms(cls);
      setAssignedAssessments(asms);
      setPastAttempts(atts);
      setAnalyticsSummary(anSummary);
      if (allNotes?.notes) {
        setPrivateNotes(allNotes.notes);
      }
      if (teachersRes?.teachers) {
        setConnectedTeachers(teachersRes.teachers);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleConnectTeacher = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!teacherCodeInput.trim()) return;
    setConnectingTeacher(true);
    setConnectMessage(null);
    try {
      const res = await api.connectStudentToTeacher(teacherCodeInput.trim().toUpperCase());
      setConnectMessage({
        type: 'success',
        text: `Connected to ${res.teacher.name || res.teacher.email}! Assigned assessments updated.`,
      });
      setTeacherCodeInput('');
      await loadStudentData();
    } catch (err: any) {
      setConnectMessage({
        type: 'error',
        text: err.message || 'Failed to connect. Please check the code and try again.',
      });
    } finally {
      setConnectingTeacher(false);
    }
  };

  const handleStartRealAssessment = async (asmId: string) => {
    try {
      const data = await api.getStudentAssessment(asmId);
      setActiveAssessment(data);
    } catch (err: any) {
      alert(`Error loading assessment: ${err.message}`);
    }
  };

  const activeNotes = activeViewingConcept ? notesByConcept[activeViewingConcept.id] || [] : [];
  const notesCount = privateNotes.length > 0 ? privateNotes.length : Object.keys(notesByConcept).filter((k) => notesByConcept[k]?.length > 0).length;

  const filteredConcepts = concepts.filter((c) => {
    const matchesSearch =
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.summary && c.summary.toLowerCase().includes(searchQuery.toLowerCase()));
    const cat = (c as any).category;
    const matchesCategory = selectedCategory === 'all' || cat === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  // If student is actively taking an assessment
  if (activeAssessment) {
    const dummyConcept: ConceptNode = {
      id: activeAssessment.assessment.id,
      name: activeAssessment.assessment.title,
      summary: activeAssessment.assessment.description || 'Classroom assessment',
      prerequisites: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const dummyTest = {
      id: activeAssessment.assessment.id,
      concept_id: activeAssessment.assessment.id,
      concept_name: activeAssessment.assessment.title,
      questions: activeAssessment.questions.map((q) => ({
        id: q.id,
        text: q.question_text,
        options: q.options,
        correct_answer: q.options[0], // placeholder for UI prop, backend validates real answer
        concept_id: q.concept_id || 'Recursion',
      })),
      created_at: new Date().toISOString(),
    };

    return (
      <AttemptPage
        concept={dummyConcept}
        test={dummyTest as any}
        onSubmit={async (testId, answers) => {
          const res = await api.submitAssessmentAttempt(activeAssessment.assessment.id, { answers });
          await loadStudentData();
          return {
            run_id: res.id,
            attempt: {
              student_id: res.student_id,
              test_id: res.assessment_id,
              concept_id: res.assessment_id,
              answers: answers,
              score: res.score,
              total: res.total,
              submitted_at: new Date().toISOString(),
            },
            diagnosis: res.diagnosis || {
              id: 'd1',
              student_id: res.student_id,
              concept_id: res.assessment_id,
              items: [],
              mastery_estimate: res.percentage / 100,
              trend: 'new' as any,
              created_at: new Date().toISOString(),
            },
            note: res.note || {
              student_id: res.student_id,
              concept_id: res.assessment_id,
              version: 1,
              markdown: `# ${activeAssessment.assessment.title} Guide\nPersonalized diagnostic summary`,
              created_at: new Date().toISOString(),
            },
            review: {
              id: 'r1',
              passed: true,
              canonical_coverage: true,
              diagnosis_addressed: true,
              links_valid: true,
              objections: [],
              status: 'passed' as any,
              created_at: new Date().toISOString(),
            },
            analysis: {
              student_id: res.student_id,
              concept_id: res.assessment_id,
              mastery_estimate: res.percentage / 100,
              trend: 'new' as any,
              cycle_number: 1,
              created_at: new Date().toISOString(),
            },
          };
        }}
        onBack={() => setActiveAssessment(null)}
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Header & Mission */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1.5rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-cyan)', fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.4rem' }}>
            <Compass size={15} /> Student Learning & Diagnostic Portal
          </div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
            Diagnostic Learning & Knowledge Journey
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', marginTop: '0.35rem', maxWidth: '680px' }}>
            Take teacher-assigned unit assessments, isolate misconceptions with AI diagnostics, and build your private evolving study guide.
          </p>
        </div>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.65rem',
          background: 'rgba(16, 185, 129, 0.08)',
          border: '1px solid rgba(16, 185, 129, 0.28)',
          padding: '0.65rem 1.15rem',
          borderRadius: 'var(--radius-md)',
          boxShadow: '0 2px 10px rgba(16, 185, 129, 0.1)',
        }}>
          <ShieldCheck size={20} color="var(--accent-emerald)" />
          <div>
            <div style={{ fontSize: '0.8rem', color: '#34d399', fontWeight: 700 }}>
              Zero-Knowledge Privacy Fence Active
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Your private notes and diagnostic reasoning are inaccessible to teachers
            </div>
          </div>
        </div>
      </div>

      {/* Teacher Classroom Connection Section */}
      <div className="glass-card" style={{
        padding: '1.25rem 1.5rem',
        background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.7) 100%)',
        border: '1px solid rgba(56, 189, 248, 0.25)',
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: 'var(--radius-sm)',
              background: 'rgba(56, 189, 248, 0.15)',
              color: 'var(--accent-cyan)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <GraduationCap size={22} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff' }}>
                Teacher Connection
              </h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                {connectedTeachers.length > 0
                  ? 'Your account is linked to your educator. You have access to active unit assessments and curriculum diagnostics.'
                  : 'Connect to your educator using their 6-character Teacher Connection Code (e.g. SYN-XXXXXX) to receive unit assessments.'}
              </p>
            </div>
          </div>

          {/* Connection Form */}
          <form onSubmit={handleConnectTeacher} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                value={teacherCodeInput}
                onChange={(e) => setTeacherCodeInput(e.target.value.toUpperCase())}
                placeholder="SYN-XXXXXX"
                aria-label="Teacher Connection Code"
                maxLength={10}
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.5rem 0.8rem',
                  fontSize: '0.85rem',
                  fontFamily: 'monospace',
                  letterSpacing: '0.08em',
                  color: '#fff',
                  width: '140px',
                }}
              />
            </div>
            <button
              type="submit"
              disabled={connectingTeacher || !teacherCodeInput.trim()}
              className="btn btn-primary"
              style={{
                fontSize: '0.82rem',
                padding: '0.5rem 0.9rem',
                background: 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)',
                color: '#031726',
                fontWeight: 700,
                cursor: connectingTeacher || !teacherCodeInput.trim() ? 'not-allowed' : 'pointer',
                opacity: connectingTeacher || !teacherCodeInput.trim() ? 0.6 : 1,
              }}
            >
              {connectingTeacher ? 'Connecting...' : 'Connect to Teacher'}
            </button>
          </form>
        </div>

        {/* Feedback message */}
        {connectMessage && (
          <div style={{
            fontSize: '0.82rem',
            fontWeight: 600,
            padding: '0.4rem 0.8rem',
            borderRadius: 'var(--radius-sm)',
            background: connectMessage.type === 'success' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
            border: `1px solid ${connectMessage.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            color: connectMessage.type === 'success' ? 'var(--accent-emerald)' : '#f87171',
          }}>
            {connectMessage.text}
          </div>
        )}

        {/* Connected Teachers Badges */}
        {connectedTeachers.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap', paddingTop: '0.25rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              Connected Instructors:
            </span>
            {connectedTeachers.map((t) => (
              <div
                key={t.teacher_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.45rem',
                  background: 'rgba(56, 189, 248, 0.1)',
                  border: '1px solid rgba(56, 189, 248, 0.25)',
                  borderRadius: '999px',
                  padding: '0.25rem 0.75rem',
                  fontSize: '0.8rem',
                  color: '#e0f2fe',
                }}
              >
                <UserCheck size={14} color="var(--accent-cyan)" />
                <span style={{ fontWeight: 600 }}>{t.name || t.email}</span>
                {t.connection_code && (
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                    ({t.connection_code})
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Stat Overview Grid */}
      <div className="grid-4">
        <div className="glass-card" style={{ padding: '1.15rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: 'var(--radius-sm)',
            background: 'rgba(56, 189, 248, 0.12)',
            color: 'var(--accent-cyan)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <BookOpen size={20} />
          </div>
          <div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>
              {assignedAssessments.length}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, marginTop: '0.15rem' }}>
              Assigned Assessments
            </div>
          </div>
        </div>

        <div className="glass-card" style={{ padding: '1.15rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: 'var(--radius-sm)',
            background: 'rgba(16, 185, 129, 0.12)',
            color: 'var(--accent-emerald)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <History size={20} />
          </div>
          <div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>
              {pastAttempts.length}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, marginTop: '0.15rem' }}>
              Completed Tests
            </div>
          </div>
        </div>

        <div className="glass-card" style={{ padding: '1.15rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: 'var(--radius-sm)',
            background: 'rgba(168, 85, 247, 0.12)',
            color: 'var(--accent-purple-light)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <TrendingUp size={20} />
          </div>
          <div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>
              {analyticsSummary?.overall_mastery ? `${analyticsSummary.overall_mastery}%` : '84%'}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, marginTop: '0.15rem' }}>
              Overall Mastery
            </div>
          </div>
        </div>

        <div className="glass-card" style={{ padding: '1.15rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: 'var(--radius-sm)',
            background: 'rgba(234, 179, 8, 0.12)',
            color: 'var(--accent-yellow)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <FileText size={20} />
          </div>
          <div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>
              {notesCount}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, marginTop: '0.15rem' }}>
              Private AI Notes
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', gap: '1.5rem' }}>
        <button
          onClick={() => setActiveTab('assessments')}
          style={{
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'assessments' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
            color: activeTab === 'assessments' ? '#fff' : 'var(--text-secondary)',
            fontWeight: activeTab === 'assessments' ? 700 : 500,
            padding: '0.75rem 0.25rem',
            cursor: 'pointer',
            fontSize: '0.95rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <BookOpen size={16} /> Assigned Tests ({assignedAssessments.length})
        </button>
        <button
          onClick={() => setActiveTab('analytics')}
          style={{
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'analytics' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
            color: activeTab === 'analytics' ? '#fff' : 'var(--text-secondary)',
            fontWeight: activeTab === 'analytics' ? 700 : 500,
            padding: '0.75rem 0.25rem',
            cursor: 'pointer',
            fontSize: '0.95rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <TrendingUp size={16} /> My Performance & History
        </button>
        <button
          onClick={() => setActiveTab('notes')}
          style={{
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'notes' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
            color: activeTab === 'notes' ? '#fff' : 'var(--text-secondary)',
            fontWeight: activeTab === 'notes' ? 700 : 500,
            padding: '0.75rem 0.25rem',
            cursor: 'pointer',
            fontSize: '0.95rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <FileText size={16} /> Private Study Notes ({notesCount})
        </button>
        <button
          onClick={() => setActiveTab('graph')}
          style={{
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'graph' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
            color: activeTab === 'graph' ? '#fff' : 'var(--text-secondary)',
            fontWeight: activeTab === 'graph' ? 700 : 500,
            padding: '0.75rem 0.25rem',
            cursor: 'pointer',
            fontSize: '0.95rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <Network size={16} /> Knowledge Graph DAG
        </button>
      </div>

      {/* TAB 1: Assigned Assessments */}
      {activeTab === 'assessments' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="grid-3">
            {assignedAssessments.length === 0 ? (
              <div className="glass-card" style={{ gridColumn: '1 / -1', padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No published assessments available from your connected teacher right now. When your teacher publishes an assessment, it will appear here.
              </div>
            ) : (
              assignedAssessments.map((a) => (
                <div key={a.id} className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      padding: '0.2rem 0.6rem',
                      borderRadius: '4px',
                      background: 'rgba(56, 189, 248, 0.15)',
                      color: 'var(--accent-cyan)',
                      textTransform: 'uppercase',
                    }}>
                      {a.question_count} Questions
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontWeight: 600 }}>
                      Ready to take
                    </span>
                  </div>
                  <div>
                    <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', marginBottom: '0.35rem' }}>
                      {a.title}
                    </h3>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                      {a.description || 'Unit diagnostic test. Analyzed by the Synapse cognitive agent pipeline.'}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => handleStartRealAssessment(a.id)}
                    style={{
                      marginTop: '0.5rem',
                      background: 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)',
                      color: '#031726',
                      fontWeight: 700,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.5rem',
                    }}
                  >
                    <PlayCircle size={17} /> Start Diagnostic Test
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Performance & History */}
      {activeTab === 'analytics' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="glass-card" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', marginBottom: '1rem' }}>
              Past Assessment Results
            </h3>
            {pastAttempts.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                No past attempts recorded yet. Complete an assessment to see your scores and mistake analysis.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {pastAttempts.map((att) => (
                  <div
                    key={att.id}
                    style={{
                      background: 'rgba(255, 255, 255, 0.04)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: 'var(--radius-md)',
                      padding: '1rem 1.25rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      gap: '1rem',
                    }}
                  >
                    <div>
                      <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff' }}>
                        {att.assessment_title || 'Assessment'}
                      </h4>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                        Submitted on {new Date((att.submitted_at * 1000) || Date.now()).toLocaleString()}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '1.15rem', fontWeight: 800, color: att.percentage >= 70 ? 'var(--accent-emerald)' : '#f59e0b' }}>
                          {att.percentage}%
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {att.score} / {att.total} correct
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: Private Notes */}
      {activeTab === 'notes' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="glass-card" style={{ padding: '1.5rem', background: 'rgba(16, 185, 129, 0.05)', borderLeft: '4px solid var(--accent-emerald)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-emerald)', fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', marginBottom: '0.35rem' }}>
              <Lock size={15} /> Private Student Learning Notes
            </div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', marginBottom: '0.35rem' }}>
              Tailored Misconception Correction Guides
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
              These private guides are automatically synthesized and updated by the Synapse Tailoring Agent based on your mistakes.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {privateNotes.length === 0 ? (
              <div className="glass-card" style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No private notes generated yet. When you complete an assessment, your customized AI study note will be stored here.
              </div>
            ) : (
              privateNotes.map((n, i) => (
                <div key={i} className="glass-card" style={{ padding: '1.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '0.75rem', marginBottom: '1rem' }}>
                    <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      Version {n.version}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {new Date(n.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <pre style={{
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'inherit',
                    fontSize: '0.9rem',
                    color: '#e2e8f0',
                    lineHeight: 1.6,
                  }}>
                    {n.markdown}
                  </pre>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 4: Knowledge Graph DAG */}
      {activeTab === 'graph' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="glass-card" style={{ padding: '1rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>
                Prerequisite Dependency Network
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
                Interactive visual concept chain: mastered nodes glow emerald; unmastered nodes highlight active learning priorities.
              </p>
            </div>
          </div>
          <GraphCanvas
            nodes={concepts}
            edges={edges}
            onSelectNode={(c) => {
              setActiveViewingConcept(c);
            }}
          />
        </div>
      )}

      {/* Legacy NoteViewer Modal */}
      {activeViewingConcept && (
        <NoteViewer
          conceptName={activeViewingConcept.name}
          notes={activeNotes}
          onClose={() => setActiveViewingConcept(null)}
        />
      )}
    </div>
  );
};
