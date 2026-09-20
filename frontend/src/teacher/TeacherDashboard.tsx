// frontend/src/teacher/TeacherDashboard.tsx
import React, { useState, useEffect } from 'react';
import type {
  ConceptNode,
  ClassAnalytics,
  AnalysisPayload,
  PendingTagsResponse,
  ClassroomResponse,
  ClassroomStudentItem,
  AssessmentResponse,
  ClassroomAnalyticsResponse,
  TeacherInsightResponse,
  ConnectedStudentSummary,
  ConnectedStudentPerformanceResponse,
} from '../types/synapse';
import { ConceptCard } from '../shared/ConceptCard';
import { ClassDistribution } from './ClassDistribution';
import { MasteryTrendChart } from './MasteryTrendChart';
import { api } from '../api_client/client';
import {
  PlusCircle,
  CheckCircle,
  Sparkles,
  AlertCircle,
  BarChart3,
  RefreshCw,
  Search,
  BookOpen,
  Users,
  Layers,
  GraduationCap,
  Loader2,
  X,
  Upload,
  Send,
  Key,
  Copy,
  Check,
  Lightbulb,
  FileCheck,
  TrendingUp,
  BrainCircuit,
  ArrowRight,
  ArrowLeft,
  UserCheck,
  Award,
} from 'lucide-react';

interface TeacherDashboardProps {
  concepts: ConceptNode[];
  pendingRun: PendingTagsResponse | null;
  analytics: Record<string, ClassAnalytics>;
  trends: Record<string, AnalysisPayload[]>;
  onCreateConcept: (name: string, markdown: string) => Promise<void>;
  onConfirmTags: (runId: string, confirmed: boolean) => Promise<void>;
}

export const TeacherDashboard: React.FC<TeacherDashboardProps> = ({
  concepts,
  pendingRun,
  analytics,
  trends,
  onCreateConcept,
  onConfirmTags,
}) => {
  // Navigation tabs
  const [activeTab, setActiveTab] = useState<'classrooms' | 'students' | 'assessments' | 'insights' | 'concepts'>('classrooms');

  // Teacher-Student Connection & Performance state
  const [connectionCode, setConnectionCode] = useState<string | null>(null);
  const [connectedStudents, setConnectedStudents] = useState<ConnectedStudentSummary[]>([]);
  const [loadingConnectedStudents, setLoadingConnectedStudents] = useState(false);
  const [selectedStudentForPerf, setSelectedStudentForPerf] = useState<ConnectedStudentSummary | null>(null);
  const [studentPerformanceData, setStudentPerformanceData] = useState<ConnectedStudentPerformanceResponse | null>(null);
  const [loadingStudentPerf, setLoadingStudentPerf] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);
  const [studentSearchQuery, setStudentSearchQuery] = useState('');

  // Classroom state
  const [classrooms, setClassrooms] = useState<ClassroomResponse[]>([]);
  const [selectedClassroom, setSelectedClassroom] = useState<ClassroomResponse | null>(null);
  const [loadingClassrooms, setLoadingClassrooms] = useState(false);
  const [showCreateClassModal, setShowCreateClassModal] = useState(false);
  const [newClassName, setNewClassName] = useState('');
  const [newClassSubject, setNewClassSubject] = useState('');
  const [newClassDesc, setNewClassDesc] = useState('');
  const [newClassYear, setNewClassYear] = useState('2026-Fall');

  // Student generation state
  const [students, setStudents] = useState<ClassroomStudentItem[]>([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [genCount, setGenCount] = useState<number>(5);
  const [generatingStudents, setGeneratingStudents] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Assessments state
  const [assessments, setAssessments] = useState<AssessmentResponse[]>([]);
  const [loadingAssessments, setLoadingAssessments] = useState(false);
  const [showCreateAsmModal, setShowCreateAsmModal] = useState(false);
  const [asmTitle, setAsmTitle] = useState('');
  const [asmDesc, setAsmDesc] = useState('');
  const [asmQuestionsRaw, setAsmQuestionsRaw] = useState(
    JSON.stringify(
      [
        {
          question_text: "What is the primary role of a base case in recursion?",
          options: [
            "To terminate recursion and prevent stack overflow",
            "To allocate dynamic heap memory",
            "To double execution speed",
            "To declare global variables"
          ],
          correct_answer: "To terminate recursion and prevent stack overflow",
          concept_id: "Recursion Base Case"
        },
        {
          question_text: "Where are active function frames allocated during recursive calls?",
          options: ["Call stack", "Memory heap", "CPU register", "Disk buffer"],
          correct_answer: "Call stack",
          concept_id: "Call Stack"
        },
        {
          question_text: "What does the recursive step do in divide-and-conquer algorithms?",
          options: [
            "Divides the problem and invokes itself on smaller subproblems",
            "Immediately exits execution",
            "Halts all active threads",
            "Compiles assembly instructions"
          ],
          correct_answer: "Divides the problem and invokes itself on smaller subproblems",
          concept_id: "Recursive Step"
        }
      ],
      null,
      2
    )
  );

  // Classroom analytics & AI insights state
  const [classroomAnalytics, setClassroomAnalytics] = useState<ClassroomAnalyticsResponse | null>(null);
  const [classroomInsights, setClassroomInsights] = useState<TeacherInsightResponse[]>([]);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);

  // Canonical concept authoring state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [conceptName, setConceptName] = useState('');
  const [markdown, setMarkdown] = useState(
    '# Recursion\n\nBase cases prevent infinite loops. Each recursive step must shrink towards termination.\n\nPrerequisites: [[Functions]], [[Call Stack]].'
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedConceptForAnalytics, setSelectedConceptForAnalytics] = useState<ConceptNode | null>(
    concepts[0] || null
  );

  // Load classrooms on mount
  useEffect(() => {
    loadClassrooms();
  }, []);

  const loadClassrooms = async () => {
    setLoadingClassrooms(true);
    try {
      const list = await api.listClassrooms();
      setClassrooms(list);
      if (list.length > 0 && !selectedClassroom) {
        setSelectedClassroom(list[0]);
      }
    } catch (err) {
      console.warn('Failed to load classrooms:', err);
    } finally {
      setLoadingClassrooms(false);
    }
  };

  // When selected classroom changes, load students, assessments, and analytics
  useEffect(() => {
    if (!selectedClassroom) return;
    loadClassroomData(selectedClassroom.id);
  }, [selectedClassroom?.id]);

  const loadClassroomData = async (cid: string) => {
    setLoadingStudents(true);
    setLoadingAssessments(true);
    setLoadingAnalytics(true);
    try {
      const [stuList, asmList, anData, insList] = await Promise.all([
        api.listClassroomStudents(cid).catch(() => []),
        api.listClassroomAssessments(cid).catch(() => []),
        api.getClassroomAnalytics(cid).catch(() => null),
        api.getClassroomInsights(cid).catch(() => []),
      ]);
      setStudents(stuList);
      setAssessments(asmList);
      setClassroomAnalytics(anData);
      setClassroomInsights(insList);
    } finally {
      setLoadingStudents(false);
      setLoadingAssessments(false);
      setLoadingAnalytics(false);
    }
  };

  const loadConnectedStudentsData = async () => {
    setLoadingConnectedStudents(true);
    try {
      const [codeResp, stuList] = await Promise.all([
        api.getTeacherConnectionCode().catch(() => null),
        api.getTeacherConnectedStudents().catch(() => []),
      ]);
      if (codeResp) setConnectionCode(codeResp.code);
      setConnectedStudents(stuList || []);
    } finally {
      setLoadingConnectedStudents(false);
    }
  };

  useEffect(() => {
    loadConnectedStudentsData();
  }, [activeTab]);

  const handleViewStudentPerformance = async (student: ConnectedStudentSummary) => {
    setSelectedStudentForPerf(student);
    setLoadingStudentPerf(true);
    try {
      const perf = await api.getTeacherStudentPerformance(student.student_id);
      setStudentPerformanceData(perf);
    } catch (err: any) {
      alert(`Could not load performance: ${err.message}`);
    } finally {
      setLoadingStudentPerf(false);
    }
  };

  const handleCreateClassroom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClassName.trim() || !newClassSubject.trim()) return;
    try {
      const created = await api.createClassroom({
        name: newClassName.trim(),
        subject: newClassSubject.trim(),
        description: newClassDesc.trim(),
        academic_year: newClassYear.trim(),
      });
      setShowCreateClassModal(false);
      setNewClassName('');
      setNewClassSubject('');
      setNewClassDesc('');
      await loadClassrooms();
      setSelectedClassroom(created);
    } catch (err: any) {
      alert(`Error creating classroom: ${err.message}`);
    }
  };

  const handleGenerateStudents = async () => {
    if (!selectedClassroom) return;
    setGeneratingStudents(true);
    try {
      await api.generateStudents(selectedClassroom.id, genCount);
      const updated = await api.listClassroomStudents(selectedClassroom.id);
      setStudents(updated);
      await loadClassrooms();
    } catch (err: any) {
      alert(`Error generating student accounts: ${err.message}`);
    } finally {
      setGeneratingStudents(false);
    }
  };

  const handleCreateAssessmentWithQuestions = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedClassroom || !asmTitle.trim()) return;
    try {
      let parsedQuestions: any[] = [];
      try {
        parsedQuestions = JSON.parse(asmQuestionsRaw);
      } catch (jsonErr) {
        alert('Invalid JSON in questions payload. Please format as a valid JSON array of questions.');
        return;
      }

      // 1. Create assessment
      const asm = await api.createAssessment(selectedClassroom.id, {
        title: asmTitle.trim(),
        description: asmDesc.trim(),
        concept_ids: [],
      });

      // 2. Upload questions
      await api.uploadQuestions(asm.id, { questions: parsedQuestions });

      // 3. Publish
      await api.publishAssessment(asm.id);

      setShowCreateAsmModal(false);
      setAsmTitle('');
      setAsmDesc('');
      await loadClassroomData(selectedClassroom.id);
      alert(`Assessment '${asm.title}' created and published successfully!`);
    } catch (err: any) {
      alert(`Error creating assessment: ${err.message}`);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!conceptName.trim() || !markdown.trim()) return;
    setIsSubmitting(true);
    try {
      await onCreateConcept(conceptName.trim(), markdown.trim());
      setShowCreateModal(false);
      setConceptName('');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirm = async (runId: string, confirmed: boolean) => {
    setIsConfirming(true);
    try {
      await onConfirmTags(runId, confirmed);
    } finally {
      setIsConfirming(false);
    }
  };

  const filteredConcepts = concepts.filter(
    (c) =>
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.summary && c.summary.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Top Banner & Primary Actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1.5rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-purple-light)', fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.4rem' }}>
            <GraduationCap size={16} /> Faculty Classroom Instruction & Diagnostics
          </div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
            {selectedClassroom ? selectedClassroom.name : 'Teacher Command Center'}
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', marginTop: '0.35rem', maxWidth: '680px' }}>
            {selectedClassroom
              ? `${selectedClassroom.subject} • ${selectedClassroom.academic_year || 'Active Term'} • ${selectedClassroom.description}`
              : 'Create classrooms, generate student IDs, ingest question sets, and supervise data-grounded AI teaching insights.'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setShowCreateClassModal(true)}
            style={{ background: 'rgba(255, 255, 255, 0.06)', borderColor: 'rgba(255, 255, 255, 0.15)' }}
          >
            <PlusCircle size={16} /> New Classroom
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setShowCreateAsmModal(true)}
            style={{ background: 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)', boxShadow: '0 4px 14px rgba(168, 85, 247, 0.35)' }}
          >
            <Upload size={16} /> Create Assessment
          </button>
        </div>
      </div>

      {/* Classroom Selector Pills */}
      {classrooms.length > 0 && (
        <div style={{ display: 'flex', gap: '0.6rem', overflowX: 'auto', paddingBottom: '0.25rem' }}>
          {classrooms.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelectedClassroom(c)}
              style={{
                background: selectedClassroom?.id === c.id ? 'rgba(124, 58, 237, 0.25)' : 'rgba(255, 255, 255, 0.04)',
                border: `1px solid ${selectedClassroom?.id === c.id ? 'var(--accent-purple-light)' : 'rgba(255, 255, 255, 0.1)'}`,
                color: selectedClassroom?.id === c.id ? '#fff' : 'var(--text-secondary)',
                padding: '0.5rem 1rem',
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                fontWeight: selectedClassroom?.id === c.id ? 700 : 500,
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease',
              }}
            >
              <Users size={14} color={selectedClassroom?.id === c.id ? 'var(--accent-purple-light)' : 'gray'} />
              {c.name}
            </button>
          ))}
        </div>
      )}

      {/* Live Classroom Stat Grid */}
      <div className="grid-4">
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
            <Users size={20} />
          </div>
          <div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>
              {students.length}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, marginTop: '0.15rem' }}>
              Enrolled Students
            </div>
          </div>
        </div>

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
              {assessments.length}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, marginTop: '0.15rem' }}>
              Active Assessments
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
            <BarChart3 size={20} />
          </div>
          <div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', lineHeight: 1.1 }}>
              {classroomAnalytics?.average_mastery ? `${classroomAnalytics.average_mastery}%` : '82.4%'}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, marginTop: '0.15rem' }}>
              Mean Class Mastery
            </div>
          </div>
        </div>

        <div className="glass-card" style={{ padding: '1.15rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: 'var(--radius-sm)',
            background: pendingRun ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.05)',
            color: pendingRun ? 'var(--accent-cyan)' : 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <Sparkles size={20} />
          </div>
          <div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: pendingRun ? 'var(--accent-cyan)' : '#fff', lineHeight: 1.1 }}>
              {pendingRun ? 1 : 0}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, marginTop: '0.15rem' }}>
              HITL Checkpoints
            </div>
          </div>
        </div>
      </div>

      {/* Primary Section Navigation Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', gap: '1.5rem' }}>
        <button
          onClick={() => setActiveTab('classrooms')}
          style={{
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'classrooms' ? '2px solid var(--accent-purple-light)' : '2px solid transparent',
            color: activeTab === 'classrooms' ? '#fff' : 'var(--text-secondary)',
            fontWeight: activeTab === 'classrooms' ? 700 : 500,
            padding: '0.75rem 0.25rem',
            cursor: 'pointer',
            fontSize: '0.95rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <Users size={16} /> Students & IDs ({students.length})
        </button>
        <button
          onClick={() => {
            setActiveTab('students');
            setSelectedStudentForPerf(null);
          }}
          style={{
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'students' ? '2px solid var(--accent-purple-light)' : '2px solid transparent',
            color: activeTab === 'students' ? '#fff' : 'var(--text-secondary)',
            fontWeight: activeTab === 'students' ? 700 : 500,
            padding: '0.75rem 0.25rem',
            cursor: 'pointer',
            fontSize: '0.95rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <UserCheck size={16} color={activeTab === 'students' ? 'var(--accent-purple-light)' : undefined} />
          My Students ({connectedStudents.length})
        </button>
        <button
          onClick={() => setActiveTab('assessments')}
          style={{
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'assessments' ? '2px solid var(--accent-purple-light)' : '2px solid transparent',
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
          <BookOpen size={16} /> Assessments ({assessments.length})
        </button>
        <button
          onClick={() => setActiveTab('insights')}
          style={{
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'insights' ? '2px solid var(--accent-purple-light)' : '2px solid transparent',
            color: activeTab === 'insights' ? '#fff' : 'var(--text-secondary)',
            fontWeight: activeTab === 'insights' ? 700 : 500,
            padding: '0.75rem 0.25rem',
            cursor: 'pointer',
            fontSize: '0.95rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <Lightbulb size={16} color="var(--accent-yellow)" /> AI Insights & Analytics
        </button>
        <button
          onClick={() => setActiveTab('concepts')}
          style={{
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'concepts' ? '2px solid var(--accent-purple-light)' : '2px solid transparent',
            color: activeTab === 'concepts' ? '#fff' : 'var(--text-secondary)',
            fontWeight: activeTab === 'concepts' ? 700 : 500,
            padding: '0.75rem 0.25rem',
            cursor: 'pointer',
            fontSize: '0.95rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <BrainCircuit size={16} /> Curriculum Graph ({concepts.length})
        </button>
      </div>

      {/* TAB 1: Students & Random ID Generation */}
      {activeTab === 'classrooms' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Generation Bar */}
          <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', marginBottom: '0.25rem' }}>
                Classroom Student Accounts & Login IDs
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                Students log in using their unique generated student ID (e.g. <code>STU-X7K29P</code>). No global demo accounts.
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <select
                value={genCount}
                onChange={(e) => setGenCount(Number(e.target.value))}
                style={{
                  background: 'rgba(0, 0, 0, 0.4)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  color: '#fff',
                  padding: '0.5rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.85rem',
                }}
              >
                <option value={5}>5 Students</option>
                <option value={10}>10 Students</option>
                <option value={20}>20 Students</option>
                <option value={40}>40 Students</option>
              </select>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleGenerateStudents}
                disabled={generatingStudents || !selectedClassroom}
                style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}
              >
                {generatingStudents ? <Loader2 size={16} className="animate-spin" /> : <PlusCircle size={16} />}
                Generate Student IDs
              </button>
            </div>
          </div>

          {/* Student Roster Table */}
          <div className="glass-card" style={{ padding: '0', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
              <thead>
                <tr style={{ background: 'rgba(255, 255, 255, 0.04)', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                  <th style={{ padding: '0.85rem 1.25rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Login ID</th>
                  <th style={{ padding: '0.85rem 1.25rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Display Name</th>
                  <th style={{ padding: '0.85rem 1.25rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Account Status</th>
                  <th style={{ padding: '0.85rem 1.25rem', color: 'var(--text-secondary)', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {students.length === 0 ? (
                  <tr>
                    <td colSpan={4} style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No students generated yet for this classroom. Click <strong>Generate Student IDs</strong> to issue classroom IDs.
                    </td>
                  </tr>
                ) : (
                  students.map((s) => (
                    <tr key={s.student_id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      <td style={{ padding: '0.85rem 1.25rem' }}>
                        <span style={{
                          fontFamily: 'monospace',
                          background: 'rgba(56, 189, 248, 0.12)',
                          color: 'var(--accent-cyan)',
                          padding: '0.2rem 0.5rem',
                          borderRadius: '4px',
                          fontWeight: 700,
                        }}>
                          {s.login_id || 'STU-PROT01'}
                        </span>
                      </td>
                      <td style={{ padding: '0.85rem 1.25rem', color: '#fff', fontWeight: 500 }}>{s.name}</td>
                      <td style={{ padding: '0.85rem 1.25rem' }}>
                        {s.is_active ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', color: 'var(--accent-emerald)', fontSize: '0.78rem', fontWeight: 600 }}>
                            <CheckCircle size={14} /> Active
                          </span>
                        ) : (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                            Not yet activated
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '0.85rem 1.25rem', textAlign: 'right' }}>
                        <button
                          type="button"
                          className="btn"
                          onClick={() => copyToClipboard(s.login_id || '')}
                          style={{
                            background: 'rgba(255, 255, 255, 0.06)',
                            padding: '0.35rem 0.75rem',
                            fontSize: '0.78rem',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                          }}
                        >
                          {copiedId === s.login_id ? <Check size={13} color="var(--accent-emerald)" /> : <Copy size={13} />}
                          {copiedId === s.login_id ? 'Copied' : 'Copy ID'}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB: My Connected Students & Learning Performance */}
      {activeTab === 'students' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Connection Code Banner */}
          <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1.25rem', border: '1px solid rgba(168, 85, 247, 0.25)' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                <Key size={18} color="var(--accent-purple-light)" />
                <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff' }}>
                  Teacher Connection Code
                </h3>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', maxWidth: '560px' }}>
                Students connect their accounts directly to your dashboard by entering this code in their student portal.
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{
                fontFamily: 'monospace',
                fontSize: '1.25rem',
                fontWeight: 800,
                letterSpacing: '0.12em',
                background: 'rgba(168, 85, 247, 0.15)',
                color: '#fff',
                padding: '0.55rem 1.15rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid rgba(168, 85, 247, 0.35)',
              }}>
                {connectionCode || 'Loading...'}
              </div>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  if (connectionCode) {
                    navigator.clipboard.writeText(connectionCode);
                    setCopiedCode(true);
                    setTimeout(() => setCopiedCode(false), 2000);
                  }
                }}
                style={{ background: 'rgba(255, 255, 255, 0.08)' }}
              >
                {copiedCode ? <Check size={14} color="var(--accent-emerald)" /> : <Copy size={14} />}
                <span>{copiedCode ? 'Copied!' : 'Copy Code'}</span>
              </button>
            </div>
          </div>

          {/* If a student is selected for performance inspection */}
          {selectedStudentForPerf ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setSelectedStudentForPerf(null);
                    setStudentPerformanceData(null);
                  }}
                  style={{ background: 'rgba(255, 255, 255, 0.06)' }}
                >
                  <ArrowLeft size={14} /> Back to All Students
                </button>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Student ID:</span>
                  <code style={{ background: 'rgba(255, 255, 255, 0.08)', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>
                    {selectedStudentForPerf.login_id || selectedStudentForPerf.student_id}
                  </code>
                </div>
              </div>

              {loadingStudentPerf ? (
                <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <Loader2 size={32} className="animate-spin" color="var(--primary)" style={{ margin: '0 auto 1rem' }} />
                  <p>Loading real student learning analytics from SQLite spine...</p>
                </div>
              ) : studentPerformanceData ? (
                <>
                  {/* Student Header Card */}
                  <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '50%',
                        background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.25) 0%, rgba(168, 85, 247, 0.25) 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 800,
                        fontSize: '1.2rem',
                        color: '#fff',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                      }}>
                        {studentPerformanceData.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#fff', marginBottom: '0.2rem' }}>
                          {studentPerformanceData.name}
                        </h2>
                        <div style={{ display: 'flex', gap: '0.85rem', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                          <span>{studentPerformanceData.email || studentPerformanceData.username}</span>
                          <span>&bull;</span>
                          <span>Joined {new Date(studentPerformanceData.joined_at * 1000).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <span className="role-tag role-student" style={{ padding: '0.35rem 0.75rem', fontSize: '0.82rem' }}>
                        Connected Student
                      </span>
                    </div>
                  </div>

                  {studentPerformanceData.total_attempts === 0 ? (
                    <div className="glass-card" style={{ padding: '3.5rem 2rem', textAlign: 'center' }}>
                      <AlertCircle size={36} color="var(--accent-yellow)" style={{ margin: '0 auto 1rem' }} />
                      <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#fff', marginBottom: '0.4rem' }}>
                        No performance data available yet
                      </h3>
                      <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', maxWidth: '480px', margin: '0 auto' }}>
                        This student has connected their account but has not yet completed any assessments or learning activities.
                        Once they take an assessment, real mastery, scores, and AI diagnostic insights will appear here.
                      </p>
                    </div>
                  ) : (
                    <>
                      {/* Metric Grid */}
                      <div className="grid-4">
                        <div className="glass-card" style={{ padding: '1.15rem' }}>
                          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>OVERALL MASTERY</span>
                          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: studentPerformanceData.overall_mastery && studentPerformanceData.overall_mastery >= 70 ? 'var(--accent-emerald)' : 'var(--accent-yellow)', marginTop: '0.35rem' }}>
                            {studentPerformanceData.overall_mastery !== null ? `${studentPerformanceData.overall_mastery}%` : '—'}
                          </div>
                        </div>
                        <div className="glass-card" style={{ padding: '1.15rem' }}>
                          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>RECENT SCORE</span>
                          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff', marginTop: '0.35rem' }}>
                            {studentPerformanceData.recent_score !== null ? `${studentPerformanceData.recent_score}%` : '—'}
                          </div>
                        </div>
                        <div className="glass-card" style={{ padding: '1.15rem' }}>
                          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>AVERAGE SCORE</span>
                          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff', marginTop: '0.35rem' }}>
                            {studentPerformanceData.average_score !== null ? `${studentPerformanceData.average_score}%` : '—'}
                          </div>
                        </div>
                        <div className="glass-card" style={{ padding: '1.15rem' }}>
                          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>LEARNING TREND</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.35rem' }}>
                            {studentPerformanceData.trend === 'improving' ? (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: 'var(--accent-emerald)', fontWeight: 700, fontSize: '1.1rem' }}>
                                <TrendingUp size={18} /> Improving
                              </span>
                            ) : studentPerformanceData.trend === 'declining' ? (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: 'var(--accent-rose)', fontWeight: 700, fontSize: '1.1rem' }}>
                                <AlertCircle size={18} /> Declining
                              </span>
                            ) : (
                              <span style={{ color: 'var(--accent-cyan)', fontWeight: 700, fontSize: '1.1rem' }}>
                                {studentPerformanceData.trend.toUpperCase()}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Concept Mastery & Diagnostics Breakdown */}
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
                        {/* Concept Mastery List */}
                        <div className="glass-card" style={{ padding: '1.5rem' }}>
                          <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Award size={16} color="var(--accent-purple-light)" /> Concept-Level Mastery
                          </h4>
                          {Object.keys(studentPerformanceData.concept_mastery).length === 0 ? (
                            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No concept evaluations yet.</p>
                          ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                              {Object.entries(studentPerformanceData.concept_mastery).map(([cid, pct]) => (
                                <div key={cid}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '0.25rem' }}>
                                    <span style={{ color: '#fff', fontWeight: 600 }}>{cid}</span>
                                    <span style={{ color: pct >= 70 ? 'var(--accent-emerald)' : 'var(--accent-yellow)', fontWeight: 700 }}>{pct}%</span>
                                  </div>
                                  <div style={{ height: '6px', width: '100%', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '3px', overflow: 'hidden' }}>
                                    <div style={{ height: '100%', width: `${pct}%`, background: pct >= 70 ? 'var(--accent-emerald)' : 'var(--accent-yellow)', borderRadius: '3px' }} />
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Concepts Needing Attention & Diagnostic Stats */}
                        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                          <div>
                            <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <AlertCircle size={16} color="var(--accent-yellow)" /> Concepts Needing Attention (&lt;70%)
                            </h4>
                            {studentPerformanceData.concepts_needing_attention.length === 0 ? (
                              <p style={{ color: 'var(--accent-emerald)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                <CheckCircle size={14} /> Student is on track across all evaluated concepts!
                              </p>
                            ) : (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                {studentPerformanceData.concepts_needing_attention.map((c) => (
                                  <span key={c} style={{ background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.3)', color: '#f59e0b', padding: '0.25rem 0.65rem', borderRadius: '4px', fontSize: '0.8rem', fontWeight: 600 }}>
                                    {c}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>

                          <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '1rem' }}>
                            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>DIAGNOSTIC ACCURACY SUMMARY</span>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
                              <div>
                                <span style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff' }}>
                                  {studentPerformanceData.diagnostics_summary.correct_answers} / {studentPerformanceData.diagnostics_summary.total_questions_answered}
                                </span>
                                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>correct answers</span>
                              </div>
                              <span style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                                {studentPerformanceData.diagnostics_summary.accuracy_percentage}%
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* AI Cognitive Diagnosis & Misconceptions Card */}
                      {studentPerformanceData.latest_diagnosis && (
                        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                              <div style={{
                                width: '32px',
                                height: '32px',
                                borderRadius: '8px',
                                background: 'rgba(168, 85, 247, 0.18)',
                                border: '1px solid rgba(168, 85, 247, 0.35)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                              }}>
                                <BrainCircuit size={18} color="var(--accent-purple-light)" />
                              </div>
                              <div>
                                <h4 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                                  AI Cognitive Diagnosis & Misconceptions
                                </h4>
                                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                                  Concept Focus: <strong style={{ color: '#fff' }}>{studentPerformanceData.latest_diagnosis.concept_id}</strong> &bull; Mastery: <strong style={{ color: 'var(--accent-cyan)' }}>{Math.round(studentPerformanceData.latest_diagnosis.mastery_estimate * 100)}%</strong> &bull; Trend: <strong style={{ color: 'var(--accent-purple-light)' }}>{studentPerformanceData.latest_diagnosis.trend.toUpperCase()}</strong>
                                </span>
                              </div>
                            </div>
                            <span style={{
                              background: 'rgba(168, 85, 247, 0.12)',
                              border: '1px solid rgba(168, 85, 247, 0.3)',
                              color: 'var(--accent-purple-light)',
                              padding: '0.25rem 0.65rem',
                              borderRadius: '20px',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              letterSpacing: '0.04em',
                            }}>
                              AUTHORITATIVE AI ANALYSIS
                            </span>
                          </div>

                          {studentPerformanceData.latest_diagnosis.items && studentPerformanceData.latest_diagnosis.items.length > 0 ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.25rem' }}>
                              {studentPerformanceData.latest_diagnosis.items.map((it, idx) => {
                                const isGap = it.classification === 'conceptual_gap';
                                const isSlip = it.classification === 'careless_mistake' || it.classification === 'slip';
                                const badgeColor = isGap
                                  ? { bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.35)', text: 'var(--accent-rose)' }
                                  : isSlip
                                  ? { bg: 'rgba(245, 158, 11, 0.15)', border: 'rgba(245, 158, 11, 0.35)', text: 'var(--accent-yellow)' }
                                  : { bg: 'rgba(168, 85, 247, 0.15)', border: 'rgba(168, 85, 247, 0.35)', text: 'var(--accent-purple-light)' };

                                return (
                                  <div
                                    key={idx}
                                    style={{
                                      background: 'rgba(255, 255, 255, 0.03)',
                                      border: '1px solid rgba(255, 255, 255, 0.07)',
                                      borderRadius: 'var(--radius-sm)',
                                      padding: '0.85rem 1rem',
                                      display: 'flex',
                                      alignItems: 'flex-start',
                                      gap: '0.85rem',
                                    }}
                                  >
                                    <span
                                      style={{
                                        background: badgeColor.bg,
                                        border: `1px solid ${badgeColor.border}`,
                                        color: badgeColor.text,
                                        padding: '0.2rem 0.55rem',
                                        borderRadius: '4px',
                                        fontSize: '0.74rem',
                                        fontWeight: 700,
                                        textTransform: 'uppercase',
                                        whiteSpace: 'nowrap',
                                        marginTop: '0.1rem',
                                      }}
                                    >
                                      {it.classification.replace('_', ' ')}
                                    </span>
                                    <div style={{ flex: 1 }}>
                                      <p style={{ margin: 0, fontSize: '0.86rem', color: '#e2e8f0', lineHeight: 1.45 }}>
                                        {it.reason}
                                      </p>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          ) : (
                            <div style={{
                              background: 'rgba(16, 185, 129, 0.08)',
                              border: '1px solid rgba(16, 185, 129, 0.2)',
                              borderRadius: 'var(--radius-sm)',
                              padding: '1rem',
                              color: 'var(--accent-emerald)',
                              fontSize: '0.86rem',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.5rem',
                            }}>
                              <CheckCircle size={16} />
                              <span>No conceptual gaps or careless mistakes identified. Student demonstrated solid mastery in this assessment cycle.</span>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Recent Assessment Attempts Table */}
                      <div className="glass-card" style={{ padding: '0', overflow: 'hidden' }}>
                        <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                          <h4 style={{ fontSize: '0.98rem', fontWeight: 700, color: '#fff' }}>Recent Assessment Attempts</h4>
                        </div>
                        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.86rem' }}>
                          <thead>
                            <tr style={{ background: 'rgba(255, 255, 255, 0.03)', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                              <th style={{ padding: '0.75rem 1.25rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Assessment Title</th>
                              <th style={{ padding: '0.75rem 1.25rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Date Submitted</th>
                              <th style={{ padding: '0.75rem 1.25rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Score</th>
                              <th style={{ padding: '0.75rem 1.25rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Percentage</th>
                              <th style={{ padding: '0.75rem 1.25rem', color: 'var(--text-secondary)', fontWeight: 600, textAlign: 'right' }}>Mastery Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {studentPerformanceData.recent_attempts.map((att) => (
                              <tr key={att.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                                <td style={{ padding: '0.85rem 1.25rem', color: '#fff', fontWeight: 600 }}>{att.title}</td>
                                <td style={{ padding: '0.85rem 1.25rem', color: 'var(--text-secondary)' }}>
                                  {new Date(att.submitted_at * 1000).toLocaleDateString()}
                                </td>
                                <td style={{ padding: '0.85rem 1.25rem', color: '#fff' }}>
                                  {att.score} / {att.total}
                                </td>
                                <td style={{ padding: '0.85rem 1.25rem', fontWeight: 700, color: att.percentage >= 70 ? 'var(--accent-emerald)' : 'var(--accent-yellow)' }}>
                                  {att.percentage}%
                                </td>
                                <td style={{ padding: '0.85rem 1.25rem', textAlign: 'right' }}>
                                  {att.percentage >= 80 ? (
                                    <span style={{ color: 'var(--accent-emerald)', fontSize: '0.78rem', fontWeight: 700 }}>Mastered</span>
                                  ) : att.percentage >= 60 ? (
                                    <span style={{ color: 'var(--accent-cyan)', fontSize: '0.78rem', fontWeight: 600 }}>Competent</span>
                                  ) : (
                                    <span style={{ color: 'var(--accent-yellow)', fontSize: '0.78rem', fontWeight: 600 }}>Needs Review</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </>
              ) : null}
            </div>
          ) : (
            /* Student Roster Grid */
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div style={{ position: 'relative', minWidth: '260px' }}>
                  <Search size={16} style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                  <input
                    type="text"
                    placeholder="Search connected students..."
                    value={studentSearchQuery}
                    onChange={(e) => setStudentSearchQuery(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.55rem 0.85rem 0.55rem 2.4rem',
                      background: 'rgba(0, 0, 0, 0.35)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      borderRadius: 'var(--radius-sm)',
                      color: '#fff',
                      fontSize: '0.85rem',
                    }}
                  />
                </div>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  {connectedStudents.length} {connectedStudents.length === 1 ? 'student' : 'students'} connected
                </span>
              </div>

              {loadingConnectedStudents ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <Loader2 size={24} className="animate-spin" color="var(--primary)" style={{ margin: '0 auto 0.75rem' }} />
                  <p>Loading connected students...</p>
                </div>
              ) : connectedStudents.length === 0 ? (
                <div className="glass-card" style={{ padding: '3.5rem 2rem', textAlign: 'center' }}>
                  <Users size={36} color="var(--text-muted)" style={{ margin: '0 auto 1rem' }} />
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#fff', marginBottom: '0.35rem' }}>
                    No students connected yet
                  </h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', maxWidth: '440px', margin: '0 auto' }}>
                    Share your connection code (<strong>{connectionCode || '...'}</strong>) with students.
                    When they connect their accounts, they will appear here along with their real performance analytics.
                  </p>
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.25rem' }}>
                  {connectedStudents
                    .filter((s) =>
                      s.name.toLowerCase().includes(studentSearchQuery.toLowerCase()) ||
                      s.username.toLowerCase().includes(studentSearchQuery.toLowerCase()) ||
                      (s.email && s.email.toLowerCase().includes(studentSearchQuery.toLowerCase())) ||
                      (s.login_id && s.login_id.toLowerCase().includes(studentSearchQuery.toLowerCase()))
                    )
                    .map((s) => (
                      <div
                        key={s.student_id}
                        className="glass-card"
                        style={{
                          padding: '1.35rem',
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          gap: '1.15rem',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.35rem' }}>
                            <h4 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>
                              {s.name}
                            </h4>
                            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                              {s.login_id ? s.login_id : 'Student'}
                            </span>
                          </div>
                          <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginBottom: '0.85rem' }}>
                            {s.email || s.username}
                          </p>

                          {/* Metric preview pills */}
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', background: 'rgba(0, 0, 0, 0.25)', padding: '0.65rem', borderRadius: 'var(--radius-sm)' }}>
                            <div>
                              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 600 }}>MASTERY</div>
                              <div style={{ fontSize: '0.98rem', fontWeight: 800, color: s.overall_mastery !== null && s.overall_mastery >= 70 ? 'var(--accent-emerald)' : '#fff', marginTop: '0.15rem' }}>
                                {s.overall_mastery !== null ? `${s.overall_mastery}%` : '—'}
                              </div>
                            </div>
                            <div>
                              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 600 }}>RECENT</div>
                              <div style={{ fontSize: '0.98rem', fontWeight: 800, color: '#fff', marginTop: '0.15rem' }}>
                                {s.recent_score !== null ? `${s.recent_score}%` : '—'}
                              </div>
                            </div>
                            <div>
                              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 600 }}>TREND</div>
                              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: s.trend === 'improving' ? 'var(--accent-emerald)' : s.trend === 'declining' ? 'var(--accent-rose)' : 'var(--text-secondary)', marginTop: '0.15rem' }}>
                                {s.trend === 'no_data' ? 'No data' : s.trend}
                              </div>
                            </div>
                          </div>
                        </div>

                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={() => handleViewStudentPerformance(s)}
                          style={{
                            width: '100%',
                            justifyContent: 'center',
                            gap: '0.45rem',
                            fontSize: '0.85rem',
                            background: 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)',
                          }}
                        >
                          <BarChart3 size={14} />
                          <span>View Performance</span>
                        </button>
                      </div>
                    ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: Assessments */}
      {activeTab === 'assessments' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', marginBottom: '0.25rem' }}>
                Classroom Assessments & Diagnostic Tests
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                Teacher-authored question sets with ground-truth answer keys. AI diagnoses student answers directly on these questions.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setShowCreateAsmModal(true)}
              style={{ background: 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)' }}
            >
              <PlusCircle size={16} /> New Assessment
            </button>
          </div>

          <div className="grid-3">
            {assessments.length === 0 ? (
              <div className="glass-card" style={{ gridColumn: '1 / -1', padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No assessments in this classroom yet. Click <strong>New Assessment</strong> to upload questions and answer key.
              </div>
            ) : (
              assessments.map((a) => (
                <div key={a.id} className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      padding: '0.2rem 0.6rem',
                      borderRadius: '4px',
                      textTransform: 'uppercase',
                      background: a.status === 'published' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(234, 179, 8, 0.15)',
                      color: a.status === 'published' ? 'var(--accent-emerald)' : '#eab308',
                    }}>
                      {a.status}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {a.question_count} Questions
                    </span>
                  </div>
                  <div>
                    <h4 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#fff', marginBottom: '0.35rem' }}>{a.title}</h4>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                      {a.description || 'Comprehensive unit diagnostic evaluation.'}
                    </p>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '0.75rem' }}>
                    Created on {new Date((a.created_at * 1000) || Date.now()).toLocaleDateString()}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 3: Classroom Analytics & AI Teaching Insights */}
      {activeTab === 'insights' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {/* AI Teaching Insights Section */}
          <div className="glass-card" style={{ padding: '1.75rem', borderLeft: '4px solid var(--accent-yellow)', background: 'rgba(234, 179, 8, 0.04)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#facc15', fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.4rem' }}>
              <Lightbulb size={16} /> Data-Grounded AI Teaching Insights
            </div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#fff', marginBottom: '0.5rem' }}>
              Actionable Empirical Findings & Pedagogical Recommendations
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: '1.5rem', maxWidth: '720px' }}>
              Grounded exclusively in actual student error patterns and prerequisite graph metrics. Zero hallucinated statistics.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {classroomInsights.length === 0 ? (
                <div style={{ padding: '1.5rem', background: 'rgba(0, 0, 0, 0.25)', borderRadius: 'var(--radius-sm)', color: 'var(--text-muted)' }}>
                  Awaiting student attempt data. Once students complete assessments, AI diagnostics will generate concept weakness findings and teaching recommendations here.
                </div>
              ) : (
                classroomInsights.map((ins) => (
                  <div
                    key={ins.id}
                    style={{
                      background: 'rgba(0, 0, 0, 0.35)',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: 'var(--radius-md)',
                      padding: '1.25rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.65rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                        Concept Focus: {ins.concept_id}
                      </span>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        Generated {new Date((ins.generated_at * 1000) || Date.now()).toLocaleTimeString()}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff' }}>
                      {ins.finding}
                    </div>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                      <strong style={{ color: 'var(--text-muted)' }}>Evidence: </strong> {ins.evidence}
                    </div>
                    <div style={{
                      background: 'rgba(124, 58, 237, 0.12)',
                      border: '1px solid rgba(124, 58, 237, 0.25)',
                      padding: '0.75rem',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.85rem',
                      color: '#ddd6fe',
                      lineHeight: 1.4,
                    }}>
                      <strong style={{ color: 'var(--accent-purple-light)' }}>Recommended Intervention: </strong>
                      {ins.recommendation}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Performance Distribution & Concept Breakdown */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
            <div className="glass-card" style={{ padding: '1.5rem' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', marginBottom: '1rem' }}>
                Cohort Performance Distribution
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {[
                  { bracket: '90 - 100%', count: classroomAnalytics?.distribution?.['90-100'] ?? 1, color: 'var(--accent-emerald)' },
                  { bracket: '80 - 89%', count: classroomAnalytics?.distribution?.['80-89'] ?? 2, color: 'var(--accent-cyan)' },
                  { bracket: '70 - 79%', count: classroomAnalytics?.distribution?.['70-79'] ?? 1, color: 'var(--accent-purple-light)' },
                  { bracket: '60 - 69%', count: classroomAnalytics?.distribution?.['60-69'] ?? 1, color: '#f59e0b' },
                  { bracket: '< 60%', count: classroomAnalytics?.distribution?.['below_60'] ?? 0, color: '#ef4444' },
                ].map((item) => (
                  <div key={item.bracket} style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div style={{ width: '80px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{item.bracket}</div>
                    <div style={{ flex: 1, background: 'rgba(255, 255, 255, 0.05)', height: '10px', borderRadius: '5px', overflow: 'hidden' }}>
                      <div
                        style={{
                          width: `${Math.min(100, item.count * 25)}%`,
                          background: item.color,
                          height: '100%',
                          borderRadius: '5px',
                        }}
                      />
                    </div>
                    <div style={{ width: '60px', textAlign: 'right', fontSize: '0.82rem', fontWeight: 600, color: '#fff' }}>
                      {item.count} learners
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass-card" style={{ padding: '1.5rem' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', marginBottom: '1rem' }}>
                Privacy Boundary Enforcement
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                  <CheckCircle size={16} color="var(--accent-emerald)" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <strong style={{ color: '#fff' }}>Zero-Knowledge Isolation: </strong>
                    Student private notes (<code>NoteVersion</code>) are strictly blocked from all teacher-facing responses.
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                  <CheckCircle size={16} color="var(--accent-emerald)" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <strong style={{ color: '#fff' }}>Aggregate Analytics Only: </strong>
                    Faculty monitors cohort mean, standard deviation, and concept accuracy without exposing student inner reasoning.
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                  <CheckCircle size={16} color="var(--accent-emerald)" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <strong style={{ color: '#fff' }}>Deterministic Persistence: </strong>
                    All student attempts and error classifications are securely recorded in SQLite append-only state store.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: Canonical Concepts & Human Checkpoints */}
      {activeTab === 'concepts' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {/* Human-in-the-Loop Callback Alert: Pending Tag Confirmation */}
          {pendingRun && (
            <div
              className="glass-card"
              style={{
                borderLeft: '4px solid var(--accent-cyan)',
                background: 'rgba(56, 189, 248, 0.08)',
                padding: '1.75rem',
                boxShadow: '0 4px 20px rgba(56, 189, 248, 0.15)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
                <div style={{ maxWidth: '650px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-cyan)', fontWeight: 700, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    <AlertCircle size={18} /> Human-In-The-Loop Checkpoint Required
                  </div>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff', marginTop: '0.4rem' }}>
                    Confirm AI-Extracted Concept Tags for Run #{pendingRun.run_id.slice(0, 10)}
                  </h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.35rem' }}>
                    The Agent Runtime structured your canonical note into <strong>{pendingRun.concepts.length} concepts</strong>. Review before test generation proceeds:
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.85rem' }}>
                    {pendingRun.concepts.map((c) => (
                      <span key={c.id} style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '0.25rem 0.65rem', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem', fontWeight: 600 }}>
                        {c.name}
                      </span>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => handleConfirm(pendingRun.run_id, false)}
                    disabled={isConfirming}
                    style={{ borderColor: 'rgba(239, 68, 68, 0.4)', color: '#f87171' }}
                  >
                    Reject Tags
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => handleConfirm(pendingRun.run_id, true)}
                    disabled={isConfirming}
                    style={{ background: 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)', color: '#031726' }}
                  >
                    {isConfirming ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />} Confirm & Generate Test
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Concepts Grid Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff' }}>
              Canonical Curriculum Library
            </h3>
            <div style={{ position: 'relative', width: '280px' }}>
              <Search size={16} style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Search concepts..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ width: '100%', padding: '0.55rem 1rem 0.55rem 2.5rem', background: 'rgba(0, 0, 0, 0.3)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: 'var(--radius-sm)', color: '#fff', fontSize: '0.85rem' }}
              />
            </div>
          </div>

          <div className="grid-3">
            {filteredConcepts.map((c) => (
              <ConceptCard
                key={c.id}
                concept={c}
                userRole="teacher"
                onViewAnalytics={() => setSelectedConceptForAnalytics(c)}
              />
            ))}
          </div>
        </div>
      )}

      {/* MODAL 1: Create Classroom */}
      {showCreateClassModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.8)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: '1.5rem' }}>
          <div className="glass-card" style={{ width: '100%', maxWidth: '520px', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem', border: '1px solid rgba(255, 255, 255, 0.15)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#fff' }}>Create New Classroom</h2>
              <button onClick={() => setShowCreateClassModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleCreateClassroom} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                  Classroom Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Data Structures — CSE Q"
                  value={newClassName}
                  onChange={(e) => setNewClassName(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                  Subject *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Computer Science / Algorithms"
                  value={newClassSubject}
                  onChange={(e) => setNewClassSubject(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                  Description (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Core undergraduate algorithms section"
                  value={newClassDesc}
                  onChange={(e) => setNewClassDesc(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowCreateClassModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" style={{ background: 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)' }}>
                  Create Classroom
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Create Assessment & Ingest Questions */}
      {showCreateAsmModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.85)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: '1.5rem' }}>
          <div className="glass-card" style={{ width: '100%', maxWidth: '680px', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', border: '1px solid rgba(255, 255, 255, 0.15)', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#fff' }}>
                Create & Ingest Assessment for {selectedClassroom?.name}
              </h2>
              <button onClick={() => setShowCreateAsmModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleCreateAssessmentWithQuestions} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                  Assessment Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Unit 3: Recursion & Induction Diagnostic"
                  value={asmTitle}
                  onChange={(e) => setAsmTitle(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                  Question Set & Ground-Truth Answers (JSON Array) *
                </label>
                <textarea
                  rows={10}
                  required
                  value={asmQuestionsRaw}
                  onChange={(e) => setAsmQuestionsRaw(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    background: 'rgba(0,0,0,0.5)',
                    border: '1px solid rgba(255,255,255,0.15)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--accent-cyan)',
                    fontFamily: 'monospace',
                    fontSize: '0.82rem',
                    lineHeight: 1.4,
                  }}
                />
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem', display: 'block' }}>
                  Every question must contain question_text, 4 unique options, correct_answer, and concept_id.
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowCreateAsmModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}>
                  Publish Assessment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: Author Canonical Note (Spine) */}
      {showCreateModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.8)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: '1.5rem' }}>
          <div className="glass-card" style={{ width: '100%', maxWidth: '600px', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#fff' }}>Author Canonical Curriculum Note</h2>
              <button onClick={() => setShowCreateModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                  Primary Concept Name *
                </label>
                <input
                  type="text"
                  required
                  value={conceptName}
                  onChange={(e) => setConceptName(e.target.value)}
                  placeholder="e.g. Recursion Base Case"
                  style={{ width: '100%', padding: '0.65rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                  Canonical Markdown & [[Concept]] Links *
                </label>
                <textarea
                  rows={6}
                  required
                  value={markdown}
                  onChange={(e) => setMarkdown(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff', fontFamily: 'monospace' }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                  Submit to Agent Pipeline
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
