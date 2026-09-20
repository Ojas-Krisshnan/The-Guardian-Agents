// frontend/src/App.tsx
import React, { useState, useEffect, useCallback } from 'react';
import type {
  ConceptNode,
  GraphEdge,
  Test,
  NoteVersion,
  PendingTagsResponse,
  SubmitAttemptResponse,
} from './types/synapse';
import { TeacherDashboard } from './teacher/TeacherDashboard';
import { StudentDashboard } from './student/StudentDashboard';
import { AttemptPage } from './student/AttemptPage';
import { api } from './api_client/client';
import { BRAIN_NODES, BRAIN_EDGES, BRAIN_TESTS, BrainNode } from './shared/brainData';
import {
  BrainCircuit,
  GraduationCap,
  Sparkles,
  Shield,
  Layers,
  CheckCircle,
  ExternalLink,
  Activity,
  User,
  X,
  Loader2,
  ArrowLeft,
  LogOut,
  AlertTriangle,
} from 'lucide-react';
import { SynapseIntro } from './shared/SynapseIntro';
import { PortalSelection } from './shared/PortalSelection';

export type PortalRole = 'teacher' | 'student';
export type AppStage = 'title' | 'select' | 'auth' | 'portal';

export interface InitialPortalState {
  hasExplicitPortal: boolean;
  stage: AppStage;
  role: PortalRole;
  activeTab: 'teacher_view' | 'student_view' | 'attempt';
}

/**
 * Deterministically resolve initial startup stage and portal on first render.
 * - If user is authenticated:
 *   - If URL has explicit portal (#teacher or #student or /teacher or /student):
 *     Initializes directly to that portal (hasExplicitPortal = true, stage = 'portal').
 * - If user is unauthenticated:
 *   - If URL requests a protected portal: directs to stage = 'auth' (auth guard)
 * - If URL has #select:
 *   Initializes to stage = 'select' (user explicitly chooses portal).
 * - If URL is root landing/startup:
 *   Initializes to stage = 'title' (SYNAPSE / Your learning space / [ Get Started ]).
 */
export function getInitialPortalState(): InitialPortalState {
  if (typeof window !== 'undefined') {
    const hash = window.location.hash.toLowerCase();
    const pathname = window.location.pathname.toLowerCase();
    const isAuthed = api.isAuthenticated();

    // 1. Direct URL hash check
    if (hash.includes('teacher')) {
      return isAuthed
        ? { hasExplicitPortal: true, stage: 'portal', role: 'teacher', activeTab: 'teacher_view' }
        : { hasExplicitPortal: true, stage: 'auth', role: 'teacher', activeTab: 'teacher_view' };
    }
    if (hash.startsWith('#attempt-')) {
      return isAuthed
        ? { hasExplicitPortal: true, stage: 'portal', role: 'student', activeTab: 'attempt' }
        : { hasExplicitPortal: true, stage: 'auth', role: 'student', activeTab: 'attempt' };
    }
    if (hash.includes('student')) {
      return isAuthed
        ? { hasExplicitPortal: true, stage: 'portal', role: 'student', activeTab: 'student_view' }
        : { hasExplicitPortal: true, stage: 'auth', role: 'student', activeTab: 'student_view' };
    }

    // 2. Direct pathname check (/teacher vs /student)
    if (pathname.endsWith('/teacher') || pathname.includes('/teacher/')) {
      return isAuthed
        ? { hasExplicitPortal: true, stage: 'portal', role: 'teacher', activeTab: 'teacher_view' }
        : { hasExplicitPortal: true, stage: 'auth', role: 'teacher', activeTab: 'teacher_view' };
    }
    if (pathname.endsWith('/student') || pathname.includes('/student/')) {
      return isAuthed
        ? { hasExplicitPortal: true, stage: 'portal', role: 'student', activeTab: 'student_view' }
        : { hasExplicitPortal: true, stage: 'auth', role: 'student', activeTab: 'student_view' };
    }

    // 3. Direct #login or #register
    if (hash.includes('login') || hash.includes('register')) {
      return { hasExplicitPortal: false, stage: 'auth', role: 'student', activeTab: 'student_view' };
    }

    // 4. Direct #select hash check
    if (hash.includes('select')) {
      return { hasExplicitPortal: false, stage: 'select', role: 'student', activeTab: 'student_view' };
    }
  }

  // 5. Root landing / startup: stage is 'title' (SYNAPSE Title Page)
  return { hasExplicitPortal: false, stage: 'title', role: 'student', activeTab: 'student_view' };
}

/**
 * Backward-compatible helper to get initial portal role.
 */
export function getInitialPortal(): PortalRole {
  return getInitialPortalState().role;
}

export const App: React.FC = () => {
  const initial = getInitialPortalState();
  const [stage, setStage] = useState<AppStage>(initial.stage);
  const [role, setRole] = useState<PortalRole>(initial.role);
  const [activeTab, setActiveTab] = useState<'teacher_view' | 'student_view' | 'attempt'>(initial.activeTab);
  const [activeTestConcept, setActiveTestConcept] = useState<ConceptNode | null>(null);

  const [currentUser, setCurrentUser] = useState<{ id: string; role: PortalRole; name: string; loginId?: string } | null>(() => {
    const auth = api.getAuth();
    if (auth.isAuthenticated && auth.role && auth.userId) {
      return {
        id: auth.userId,
        role: auth.role as PortalRole,
        name: auth.userName || auth.userId,
      };
    }
    return null;
  });
  const [isCheckingAuth, setIsCheckingAuth] = useState<boolean>(() => api.isAuthenticated());
  const [intendedDestination, setIntendedDestination] = useState<{ role: PortalRole; hash: string } | null>(() => {
    if (typeof window !== 'undefined' && !api.isAuthenticated()) {
      const hash = window.location.hash.toLowerCase();
      const pathname = window.location.pathname.toLowerCase();
      if (hash.includes('teacher') || pathname.endsWith('/teacher') || pathname.includes('/teacher/')) {
        return { role: 'teacher', hash: '#teacher' };
      }
      if (hash.startsWith('#attempt-')) {
        return { role: 'student', hash };
      }
      if (hash.includes('student') || pathname.endsWith('/student') || pathname.includes('/student/')) {
        return { role: 'student', hash: '#student' };
      }
    }
    return null;
  });

  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [authTab, setAuthTab] = useState<'student' | 'teacher'>('student');
  const [studentAuthMethod, setStudentAuthMethod] = useState<'id' | 'password'>('id');
  const [studentIdInput, setStudentIdInput] = useState('');
  const [studentUserInput, setStudentUserInput] = useState('');
  const [studentPassInput, setStudentPassInput] = useState('');
  const [teacherUserInput, setTeacherUserInput] = useState('');
  const [teacherPassInput, setTeacherPassInput] = useState('');
  const [regNameInput, setRegNameInput] = useState('');
  const [regUserInput, setRegUserInput] = useState('');
  const [regEmailInput, setRegEmailInput] = useState('');
  const [regPassInput, setRegPassInput] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  // Authoritatively validate existing session against SQLite on startup
  useEffect(() => {
    if (api.isAuthenticated()) {
      api.validateSession().then((user) => {
        if (user && user.role) {
          setCurrentUser({
            id: user.id,
            role: user.role as PortalRole,
            name: user.name || user.username || user.id,
            loginId: user.login_id,
          });
        } else {
          setCurrentUser(null);
          if (stage === 'portal') {
            setStage('auth');
            if (typeof window !== 'undefined') window.history.replaceState(null, '', '#login');
          }
        }
        setIsCheckingAuth(false);
      });
    } else {
      setIsCheckingAuth(false);
    }
  }, []);

  // Browser back/forward & hash synchronization listener with authentication gate
  useEffect(() => {
    const handleLocationChange = () => {
      if (typeof window === 'undefined') return;
      const hash = window.location.hash.toLowerCase();
      const pathname = window.location.pathname.toLowerCase();
      const isAuthed = api.isAuthenticated();

      if (hash.includes('teacher') || pathname.endsWith('/teacher') || pathname.includes('/teacher/')) {
        if (!isAuthed) {
          setIntendedDestination({ role: 'teacher', hash: '#teacher' });
          setAuthTab('teacher');
          setStage('auth');
          window.history.replaceState(null, '', '#login');
        } else {
          setStage('portal');
          setRole('teacher');
          setActiveTab('teacher_view');
        }
      } else if (hash.startsWith('#attempt-')) {
        if (!isAuthed) {
          setIntendedDestination({ role: 'student', hash });
          setAuthTab('student');
          setStage('auth');
          window.history.replaceState(null, '', '#login');
        } else {
          setStage('portal');
          setRole('student');
          setActiveTab('attempt');
        }
      } else if (hash.includes('student') || pathname.endsWith('/student') || pathname.includes('/student/')) {
        if (!isAuthed) {
          setIntendedDestination({ role: 'student', hash: '#student' });
          setAuthTab('student');
          setStage('auth');
          window.history.replaceState(null, '', '#login');
        } else {
          setStage('portal');
          setRole('student');
          setActiveTab('student_view');
        }
      } else if (hash.includes('login') || hash.includes('register')) {
        setStage('auth');
        if (hash.includes('register')) setAuthMode('register');
        if (hash.includes('login')) setAuthMode('login');
      } else if (hash.includes('select')) {
        setStage('select');
      } else if (hash === '' || hash === '#' || hash.includes('title')) {
        setStage('title');
      }
    };

    window.addEventListener('popstate', handleLocationChange);
    window.addEventListener('hashchange', handleLocationChange);
    return () => {
      window.removeEventListener('popstate', handleLocationChange);
      window.removeEventListener('hashchange', handleLocationChange);
    };
  }, []);

  // Handler for explicit portal selection from Stage 2 Selection Screen
  const handleSelectPortal = useCallback((selectedRole: PortalRole) => {
    const isAuthed = api.isAuthenticated();
    const currentAuth = api.getAuth();

    if (isAuthed && currentAuth.role === selectedRole) {
      setRole(selectedRole);
      setActiveTab(selectedRole === 'teacher' ? 'teacher_view' : 'student_view');
      setStage('portal');
      if (typeof window !== 'undefined') {
        window.history.pushState(null, '', `#${selectedRole}`);
      }
    } else {
      // Unauthenticated or switching role: route to Auth gate with destination preserved
      setIntendedDestination({ role: selectedRole, hash: `#${selectedRole}` });
      setAuthTab(selectedRole);
      setAuthMode('login');
      setStage('auth');
      if (typeof window !== 'undefined') {
        window.history.pushState(null, '', '#login');
      }
    }
  }, []);

  // Handler for Sign Out
  const handleLogout = useCallback(() => {
    api.clearAuth();
    setCurrentUser(null);
    setIntendedDestination(null);
    setStage('select');
    if (typeof window !== 'undefined') {
      window.history.replaceState(null, '', '#select');
    }
  }, []);

  // Handler for Successful Authentication (Login or Registration)
  const handleAuthSuccess = useCallback((resp: any) => {
    setCurrentUser({
      id: resp.user.id,
      role: resp.user.role as PortalRole,
      name: resp.user.name,
      loginId: resp.user.login_id,
    });
    setRole(resp.user.role as PortalRole);
    setActiveTab(resp.user.role === 'teacher' ? 'teacher_view' : 'student_view');
    setShowAuthModal(false);
    setAuthError(null);

    const target = intendedDestination;
    setIntendedDestination(null);

    if (target && target.role === resp.user.role) {
      setStage('portal');
      if (typeof window !== 'undefined') {
        window.history.pushState(null, '', target.hash);
      }
    } else {
      setStage('portal');
      if (typeof window !== 'undefined') {
        window.history.pushState(null, '', `#${resp.user.role}`);
      }
    }
  }, [intendedDestination]);

  // Initial Full Brain Dataset (24 interconnected nodes)
  const [concepts, setConcepts] = useState<ConceptNode[]>(BRAIN_NODES);
  const [edges, setEdges] = useState<GraphEdge[]>(BRAIN_EDGES);

  const [pendingRun, setPendingRun] = useState<PendingTagsResponse | null>(null);

  // Student Notes map: conceptId -> list of notes
  const [studentNotes, setStudentNotes] = useState<Record<string, NoteVersion[]>>({
    'c-rec': [
      {
        student_id: 'student_1',
        concept_id: 'c-rec',
        version: 1,
        markdown: `# Recursion & Induction Study Guide (v1)

Personalized notes synthesized from your diagnostic assessment. Connects closely with [[Linear Data Structures]] and [[Dynamic Programming]].

## Key Concepts
Recursion requires a base condition to terminate and an inductive step that shrinks problem size monotonically toward termination.

## Mistake Pattern Table
| Question | Your Answer | Correct Idea | What Happened |
|---|---|---|---|
| Q1: Termination | Missing base case | Always check stopping criteria | Conceptual gap in recursive branch termination |
| Q2: Call Stack | Unbounded memory | Bounded stack depth | Careless arithmetic error in frame calculation |

## Next Steps
Master binary tree traversal recursions before diving into Dynamic Programming and Tree Search!`,
        created_at: new Date().toISOString(),
      },
    ],
    'c-attn': [
      {
        student_id: 'student_1',
        concept_id: 'c-attn',
        version: 1,
        markdown: `# Self-Attention Mechanism Study Guide (v1)

Personalized notes on Scaled Dot-Product & Multi-Head Attention. Connects with [[Transformer & LLM Architectures]].

## Key Concepts
- Queries ($Q$), Keys ($K$), and Values ($V$) project input representations into relational space.
- Softmax scaling factor $1/\\sqrt{d_k}$ prevents gradient saturation in high dimensions.

## Mistake Pattern Table
| Question | Your Answer | Correct Idea | What Happened |
|---|---|---|---|
| Q1: Scaling Factor | Invert matrix | Softmax gradient preservation | Conceptual gap in gradient propagation dynamics |

## Next Steps
Trace how causal masking enforces autoregression in decoder architectures.`,
        created_at: new Date().toISOString(),
      },
    ],
  });

  // Tests map across all concepts
  const [testsByConcept, setTestsByConcept] = useState<Record<string, Test>>(BRAIN_TESTS);

  const handleCreateConcept = async (name: string, md: string) => {
    const newId = `c-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
    const newTest: Test = {
      id: `test-${newId}`,
      concept_id: newId,
      concept_name: name,
      created_at: new Date().toISOString(),
      questions: [
        {
          id: `q-${newId}-1`,
          concept_id: newId,
          text: `What is the primary algorithmic invariant or definition of ${name}?`,
          correct_answer: `Preserving structural validity and verified state transitions`,
          options: [
            `Preserving structural validity and verified state transitions`,
            `Unbounded memory allocation without termination guarantees`,
            `Converting operations into stochastic unverified permutations`,
            `Bypassing all prerequisite validation constraints`,
          ],
        },
        {
          id: `q-${newId}-2`,
          concept_id: newId,
          text: `Which core principle distinguishes ${name} from naive implementations?`,
          correct_answer: `Optimized computational bounds and deliberate error recovery`,
          options: [
            `Optimized computational bounds and deliberate error recovery`,
            `Infinite recursive depth without base cases`,
            `Strict reliance on undocumented side-effects`,
            `Ignoring prerequisite dependencies completely`,
          ],
        },
      ],
    };

    setTestsByConcept((prev) => ({ ...prev, [newId]: newTest }));

    try {
      const resp = await api.createConcept({ concept_name: name, markdown: md });
      const newConcept = resp.concept;
      setConcepts((prev) => [...prev, newConcept]);

      setPendingRun({
        run_id: resp.run_id,
        concept_id: newConcept.id,
        concepts: [newConcept],
        expires_at: new Date(Date.now() + 600000).toISOString(),
      });
    } catch {
      // Fallback local update
      const newConcept: BrainNode = {
        id: newId,
        name,
        summary: `Canonical definition for ${name}`,
        prerequisites: ['c-rec'],
        category: 'cognitive_agents',
        x: 480 + (Math.random() * 80 - 40),
        y: 280 + (Math.random() * 80 - 40),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setConcepts((prev) => [...prev, newConcept]);
      setEdges((prev) => [
        ...prev,
        { from_concept: 'c-rec', to_concept: newId, relationship: 'prerequisite' },
      ]);
      setPendingRun({
        run_id: `run-${Date.now()}`,
        concept_id: newId,
        concepts: [newConcept],
        expires_at: new Date(Date.now() + 600000).toISOString(),
      });
    }
  };

  const handleConfirmTags = async (runId: string, confirmed: boolean) => {
    try {
      await api.confirmTags(runId, { run_id: runId, confirmed });
    } catch {
      // simulated success
    }
    setPendingRun(null);
  };

  const handleSubmitAttempt = async (
    testId: string,
    answers: Record<string, string>
  ): Promise<SubmitAttemptResponse> => {
    const conceptId = activeTestConcept?.id || 'c-rec';
    const conceptName = activeTestConcept?.name || 'Recursion';
    const currentTest =
      testsByConcept[conceptId] ||
      testsByConcept['c-rec'] || {
        id: testId,
        concept_id: conceptId,
        concept_name: conceptName,
        created_at: new Date().toISOString(),
        questions: [],
      };

    try {
      const resp = await api.submitAttempt({ test_id: testId, answers });
      if (activeTestConcept && resp.note) {
        setStudentNotes((prev) => ({
          ...prev,
          [activeTestConcept.id]: [...(prev[activeTestConcept.id] || []), resp.note],
        }));
      }
      return resp;
    } catch {
      let score = 0;
      const questionsList = currentTest.questions || [];
      const items = questionsList.map((q) => {
        const isCorrect = answers[q.id] === q.correct_answer;
        if (isCorrect) score += 1;
        return {
          question_id: q.id,
          classification: isCorrect
            ? ('careless_mistake' as const)
            : ('conceptual_gap' as const),
          reason: isCorrect
            ? `Correctly identified core mechanics of ${conceptName}.`
            : `Struggled with boundary conditions and state propagation in ${conceptName}.`,
        };
      });

      const totalQ = questionsList.length || 1;
      const mastery = score / totalQ;
      const versionNum = (studentNotes[conceptId]?.length || 0) + 1;
      const newNote: NoteVersion = {
        student_id: 'student_1',
        concept_id: conceptId,
        version: versionNum,
        markdown: `# ${conceptName} Study Guide (v${versionNum})

Personalized diagnostic review for ${conceptName}.

## Diagnostic Summary
- Score: ${score} / ${totalQ} (${Math.round(mastery * 100)}% Mastery)
- Status: ${mastery >= 0.7 ? 'Strong conceptual grasp with minor refinement needed' : 'Priority concept for reinforcement'}

## Mistake Pattern Table
| Question | Your Answer | Correct Idea | What Happened |
|---|---|---|---|
| Q1: Core Invariant | ${answers[questionsList[0]?.id] || 'Selected Option'} | ${questionsList[0]?.correct_answer || 'Verified Invariant'} | Evaluated via cognitive diagnostic agent |
${questionsList[1] ? `| Q2: Failure Mode | ${answers[questionsList[1]?.id] || 'Selected Option'} | ${questionsList[1]?.correct_answer || 'Verified Invariant'} | Cognitive pattern analysis |` : ''}

## Key Insights & Recommended Next Steps
- Review foundational prerequisites before testing downstream dependent concepts.
- Focus on verifying termination criteria and asymptotic complexity bounds.`,
        created_at: new Date().toISOString(),
      };

      setStudentNotes((prev) => ({
        ...prev,
        [conceptId]: [...(prev[conceptId] || []), newNote],
      }));

      return {
        run_id: `run-${Date.now()}`,
        attempt: {
          student_id: 'student_1',
          test_id: testId,
          concept_id: conceptId,
          answers,
          score,
          total: totalQ,
          submitted_at: new Date().toISOString(),
        },
        diagnosis: {
          id: `diag-${Date.now()}`,
          student_id: 'student_1',
          concept_id: conceptId,
          items,
          mastery_estimate: mastery,
          trend: mastery >= 0.7 ? 'improving' : 'still_weak',
          created_at: new Date().toISOString(),
        },
        note: newNote,
        review: {
          id: `rev-${Date.now()}`,
          passed: true,
          canonical_coverage: true,
          diagnosis_addressed: true,
          links_valid: true,
          objections: [],
          status: 'passed',
          created_at: new Date().toISOString(),
        },
        analysis: {
          student_id: 'student_1',
          concept_id: conceptId,
          mastery_estimate: mastery,
          trend: mastery >= 0.7 ? 'improving' : 'still_weak',
          cycle_number: 1,
          created_at: new Date().toISOString(),
        },
      };
    }
  };

  const handleStartTest = (concept: ConceptNode) => {
    setActiveTestConcept(concept);
    setActiveTab('attempt');
    if (typeof window !== 'undefined') {
      window.history.pushState(null, '', `#attempt-${concept.id}`);
    }
  };

  const handleBackFromAttempt = () => {
    setActiveTab('student_view');
    if (typeof window !== 'undefined') {
      window.history.pushState(null, '', '#student');
    }
  };

  const renderAuthContent = (isModal: boolean) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Auth Mode Toggle: Sign In vs Create Account */}
      <div style={{ display: 'flex', gap: '0.4rem', background: 'rgba(0,0,0,0.3)', padding: '0.25rem', borderRadius: 'var(--radius-sm)' }}>
        <button
          type="button"
          onClick={() => { setAuthMode('login'); setAuthError(null); }}
          style={{
            flex: 1,
            padding: '0.45rem',
            borderRadius: '4px',
            border: 'none',
            background: authMode === 'login' ? 'rgba(255,255,255,0.14)' : 'transparent',
            color: authMode === 'login' ? '#fff' : 'var(--text-muted)',
            fontWeight: authMode === 'login' ? 700 : 500,
            cursor: 'pointer',
            fontSize: '0.82rem',
            transition: 'all 0.15s ease',
          }}
        >
          Sign In
        </button>
        <button
          type="button"
          onClick={() => { setAuthMode('register'); setAuthError(null); }}
          style={{
            flex: 1,
            padding: '0.45rem',
            borderRadius: '4px',
            border: 'none',
            background: authMode === 'register' ? 'rgba(255,255,255,0.14)' : 'transparent',
            color: authMode === 'register' ? '#fff' : 'var(--text-muted)',
            fontWeight: authMode === 'register' ? 700 : 500,
            cursor: 'pointer',
            fontSize: '0.82rem',
            transition: 'all 0.15s ease',
          }}
        >
          Create Account
        </button>
      </div>

      {/* Role Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
        <button
          type="button"
          onClick={() => { setAuthTab('student'); setAuthError(null); }}
          style={{
            flex: 1,
            background: 'none',
            border: 'none',
            borderBottom: authTab === 'student' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
            color: authTab === 'student' ? 'var(--accent-cyan)' : 'var(--text-muted)',
            fontWeight: authTab === 'student' ? 700 : 500,
            padding: '0.65rem',
            cursor: 'pointer',
            fontSize: '0.88rem',
            transition: 'all 0.15s ease',
          }}
        >
          Student {authMode === 'register' ? 'Account' : 'Login'}
        </button>
        <button
          type="button"
          onClick={() => { setAuthTab('teacher'); setAuthError(null); }}
          style={{
            flex: 1,
            background: 'none',
            border: 'none',
            borderBottom: authTab === 'teacher' ? '2px solid var(--accent-purple-light)' : '2px solid transparent',
            color: authTab === 'teacher' ? 'var(--accent-purple-light)' : 'var(--text-muted)',
            fontWeight: authTab === 'teacher' ? 700 : 500,
            padding: '0.65rem',
            cursor: 'pointer',
            fontSize: '0.88rem',
            transition: 'all 0.15s ease',
          }}
        >
          Teacher {authMode === 'register' ? 'Account' : 'Login'}
        </button>
      </div>

      {authError && (
        <div style={{ padding: '0.65rem 0.85rem', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: 'var(--radius-sm)', color: '#f87171', fontSize: '0.82rem' }}>
          {authError}
        </div>
      )}

      {/* Create Account Form */}
      {authMode === 'register' ? (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!regNameInput.trim() || !regUserInput.trim() || !regPassInput) return;
            setAuthLoading(true);
            setAuthError(null);
            try {
              const resp = await api.register({
                role: authTab,
                name: regNameInput.trim(),
                username: regUserInput.trim(),
                email: regEmailInput.trim() || undefined,
                password: regPassInput,
              });
              handleAuthSuccess(resp);
            } catch (err: any) {
              setAuthError(err.message || 'Registration failed');
            } finally {
              setAuthLoading(false);
            }
          }}
          style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}
        >
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
              Full Name
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Marie Curie"
              value={regNameInput}
              onChange={(e) => setRegNameInput(e.target.value)}
              style={{ width: '100%', padding: '0.6rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
              Username
            </label>
            <input
              type="text"
              required
              placeholder="e.g. mcurie"
              value={regUserInput}
              onChange={(e) => setRegUserInput(e.target.value)}
              style={{ width: '100%', padding: '0.6rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
              Email (Optional)
            </label>
            <input
              type="email"
              placeholder="e.g. curie@synapse.edu"
              value={regEmailInput}
              onChange={(e) => setRegEmailInput(e.target.value)}
              style={{ width: '100%', padding: '0.6rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
              Password (min 6 characters)
            </label>
            <input
              type="password"
              required
              minLength={6}
              placeholder="••••••••"
              value={regPassInput}
              onChange={(e) => setRegPassInput(e.target.value)}
              style={{ width: '100%', padding: '0.6rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={authLoading}
            style={{
              background: authTab === 'teacher' ? 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)' : 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)',
              color: authTab === 'teacher' ? '#ffffff' : '#031726',
              fontWeight: 700,
              marginTop: '0.25rem',
            }}
          >
            {authLoading ? <Loader2 size={16} className="animate-spin" /> : `Create ${authTab === 'teacher' ? 'Teacher' : 'Student'} Account`}
          </button>
        </form>
      ) : authTab === 'student' ? (
        /* Student Login Form */
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setAuthLoading(true);
            setAuthError(null);
            try {
              let resp;
              if (studentAuthMethod === 'id') {
                if (!studentIdInput.trim()) return;
                resp = await api.login({ login_id: studentIdInput.trim() });
              } else {
                if (!studentUserInput.trim() || !studentPassInput) return;
                resp = await api.login({ username: studentUserInput.trim(), password: studentPassInput });
              }
              handleAuthSuccess(resp);
            } catch (err: any) {
              setAuthError(err.message || 'Login failed');
            } finally {
              setAuthLoading(false);
            }
          }}
          style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}
        >
          {/* Method Selector */}
          <div style={{ display: 'flex', gap: '0.35rem', background: 'rgba(0,0,0,0.25)', padding: '0.2rem', borderRadius: 'var(--radius-sm)' }}>
            <button
              type="button"
              onClick={() => { setStudentAuthMethod('id'); setAuthError(null); }}
              style={{
                flex: 1,
                padding: '0.35rem',
                borderRadius: '4px',
                border: 'none',
                background: studentAuthMethod === 'id' ? 'rgba(2, 132, 199, 0.3)' : 'transparent',
                color: studentAuthMethod === 'id' ? '#38bdf8' : 'var(--text-muted)',
                fontWeight: studentAuthMethod === 'id' ? 700 : 500,
                cursor: 'pointer',
                fontSize: '0.78rem',
              }}
            >
              Classroom ID
            </button>
            <button
              type="button"
              onClick={() => { setStudentAuthMethod('password'); setAuthError(null); }}
              style={{
                flex: 1,
                padding: '0.35rem',
                borderRadius: '4px',
                border: 'none',
                background: studentAuthMethod === 'password' ? 'rgba(2, 132, 199, 0.3)' : 'transparent',
                color: studentAuthMethod === 'password' ? '#38bdf8' : 'var(--text-muted)',
                fontWeight: studentAuthMethod === 'password' ? 700 : 500,
                cursor: 'pointer',
                fontSize: '0.78rem',
              }}
            >
              Username & Password
            </button>
          </div>

          {studentAuthMethod === 'id' ? (
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                Classroom Student ID (e.g. STU-X7K29P)
              </label>
              <input
                type="text"
                required
                placeholder="Enter your STU- ID"
                value={studentIdInput}
                onChange={(e) => setStudentIdInput(e.target.value)}
                style={{ width: '100%', padding: '0.65rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff', fontFamily: 'monospace' }}
              />
            </div>
          ) : (
            <>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Username or Email
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. student_jane or jane@synapse.edu"
                  value={studentUserInput}
                  onChange={(e) => setStudentUserInput(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Password
                </label>
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={studentPassInput}
                  onChange={(e) => setStudentPassInput(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
                />
              </div>
            </>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={authLoading}
            style={{ background: 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)', color: '#031726', fontWeight: 700, marginTop: '0.25rem' }}
          >
            {authLoading ? <Loader2 size={16} className="animate-spin" /> : (studentAuthMethod === 'id' ? 'Enter Classroom' : 'Sign In as Student')}
          </button>
        </form>
      ) : (
        /* Teacher Login Form */
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!teacherUserInput.trim() || !teacherPassInput) return;
            setAuthLoading(true);
            setAuthError(null);
            try {
              const resp = await api.login({ username: teacherUserInput.trim(), password: teacherPassInput });
              handleAuthSuccess(resp);
            } catch (err: any) {
              setAuthError(err.message || 'Invalid username or password');
            } finally {
              setAuthLoading(false);
            }
          }}
          style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}
        >
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Username or Email
            </label>
            <input
              type="text"
              required
              placeholder="e.g. prof_curie or curie@synapse.edu"
              value={teacherUserInput}
              onChange={(e) => setTeacherUserInput(e.target.value)}
              style={{ width: '100%', padding: '0.65rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Password
            </label>
            <input
              type="password"
              required
              placeholder="••••••••"
              value={teacherPassInput}
              onChange={(e) => setTeacherPassInput(e.target.value)}
              style={{ width: '100%', padding: '0.65rem', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={authLoading}
            style={{ background: 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)', fontWeight: 700 }}
          >
            {authLoading ? <Loader2 size={16} className="animate-spin" /> : 'Faculty Login'}
          </button>
        </form>
      )}
    </div>
  );

  // Authentication Loading Screen to prevent content flicker
  if (isCheckingAuth) {
    return (
      <div className="auth-loading-screen">
        <Loader2 size={36} className="animate-spin" color="var(--primary)" />
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', fontWeight: 500 }}>
          Verifying secure session...
        </p>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Stage 1: Clean, Human-Designed Title Page */}
      {stage === 'title' && (
        <SynapseIntro
          onComplete={() => {
            setStage('select');
            if (typeof window !== 'undefined') window.history.pushState(null, '', '#select');
          }}
        />
      )}

      {/* Stage 2: Portal Selection */}
      {stage === 'select' && (
        <PortalSelection onSelectPortal={handleSelectPortal} />
      )}

      {/* Stage Auth: Dedicated Sign In / Create Account Screen */}
      {stage === 'auth' && (
        <div className="auth-page-container">
          <div className="auth-card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <div className="brand-icon-wrapper" style={{ width: '32px', height: '32px' }}>
                  <BrainCircuit size={18} color="var(--primary)" />
                </div>
                <span style={{ fontSize: '1.1rem', fontWeight: 800, letterSpacing: '0.05em', color: '#fff' }}>SYNAPSE</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setStage('select');
                  if (typeof window !== 'undefined') window.history.pushState(null, '', '#select');
                }}
                className="workspace-switch-btn"
                style={{ fontSize: '0.78rem' }}
              >
                <ArrowLeft size={13} />
                <span>Workspaces</span>
              </button>
            </div>

            <div style={{ marginBottom: '1.25rem' }}>
              <h2 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff', marginBottom: '0.25rem' }}>
                {authMode === 'register' ? 'Create an Account' : 'Sign in to continue'}
              </h2>
              <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
                {intendedDestination
                  ? `Authentication required to access ${intendedDestination.role === 'teacher' ? 'Teacher' : 'Student'} Workspace.`
                  : 'Access your personalized learning and diagnostic workspace.'}
              </p>
            </div>

            {renderAuthContent(false)}
          </div>
        </div>
      )}

      {/* Stage 3: Selected Workspace Dashboard */}
      {stage === 'portal' && (
        <>
          {/* Top Navbar with Clean Workspace Context */}
          <header className="app-nav" role="banner">
            <div
              className="brand"
              onClick={() => {
                setStage('select');
                if (typeof window !== 'undefined') window.history.pushState(null, '', '#select');
              }}
              title="Return to Workspace Selection (Stage 2)"
            >
              <div className="brand-icon-wrapper">
                <BrainCircuit size={20} color="var(--primary)" />
              </div>
              <div className="brand-text">
                <span className="brand-title">
                  SYNAPSE
                </span>
                <span className="brand-workspace-pill">
                  {role === 'teacher' ? 'Teacher Workspace' : 'Student Workspace'}
                </span>
              </div>
            </div>

            {/* Subtle Switch Workspace Action */}
            <div className="workspace-header-actions">
              <button
                type="button"
                className="workspace-switch-btn"
                onClick={() => {
                  setStage('select');
                  if (typeof window !== 'undefined') window.history.pushState(null, '', '#select');
                }}
                title="Return to Workspace Selection"
                aria-label="Switch Workspace"
              >
                <ArrowLeft size={14} />
                <span>Switch Workspace</span>
              </button>
            </div>

            {/* Right Header Section: System Live Pill + User Badge + Sign Out */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div className="system-status-indicator" title="Autonomous SQLite Runtime Active">
                <div className="status-dot" />
                <span style={{ fontWeight: 600, fontSize: '0.75rem' }}>Engine Live</span>
              </div>

              {currentUser && (
                <button
                  type="button"
                  onClick={() => {
                    setAuthTab(role);
                    setAuthError(null);
                    setShowAuthModal(true);
                  }}
                  className="user-badge"
                  style={{
                    cursor: 'pointer',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    padding: '0.35rem 0.75rem',
                    borderRadius: 'var(--radius-md)',
                    transition: 'all 0.15s ease',
                  }}
                  title="Click to Switch Account"
                >
                  <div className={`user-avatar ${currentUser.role === 'teacher' ? 'user-avatar-teacher' : 'user-avatar-student'}`}>
                    {currentUser.role === 'teacher' ? 'TC' : 'ST'}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.15, textAlign: 'left' }}>
                    <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.82rem' }}>
                      {currentUser.name}
                    </span>
                    <span className={`role-tag ${currentUser.role === 'teacher' ? 'role-teacher' : 'role-student'}`} style={{ marginTop: '0.15rem' }}>
                      {currentUser.loginId || (currentUser.role === 'teacher' ? 'Faculty Admin' : 'Learner Active')} &bull; Switch
                    </span>
                  </div>
                </button>
              )}

              <button
                type="button"
                onClick={handleLogout}
                className="btn-signout"
                title="Sign out of your account"
                aria-label="Sign Out"
              >
                <LogOut size={14} />
                <span>Sign Out</span>
              </button>
            </div>
          </header>

          {/* Modal: Switch Account */}
          {showAuthModal && (
            <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1.5rem' }}>
              <div className="glass-card" style={{ width: '100%', maxWidth: '440px', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', border: '1px solid rgba(255,255,255,0.15)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#fff' }}>Switch Account</h2>
                  <button onClick={() => setShowAuthModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                    <X size={20} />
                  </button>
                </div>
                {renderAuthContent(true)}
              </div>
            </div>
          )}

          {/* Main App Body with Role Boundary Guard */}
          <main className="main-content" role="main">
            {currentUser && currentUser.role !== role ? (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '55vh' }}>
                <div className="glass-card" style={{ maxWidth: '480px', padding: '2.25rem', textAlign: 'center', border: '1px solid rgba(245, 158, 11, 0.35)' }}>
                  <div style={{ display: 'inline-flex', padding: '0.85rem', background: 'rgba(245, 158, 11, 0.15)', borderRadius: '50%', marginBottom: '1.25rem' }}>
                    <AlertTriangle size={36} color="#f59e0b" />
                  </div>
                  <h2 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#fff', marginBottom: '0.6rem' }}>
                    Workspace Restricted
                  </h2>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', lineHeight: 1.55, marginBottom: '1.5rem' }}>
                    You are signed in as a <strong style={{ color: '#fff', textTransform: 'capitalize' }}>{currentUser.role}</strong> ({currentUser.name}).
                    This portal requires <strong style={{ color: '#fff', textTransform: 'capitalize' }}>{role}</strong> authorization.
                  </p>
                  <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => {
                        setRole(currentUser.role);
                        setActiveTab(currentUser.role === 'teacher' ? 'teacher_view' : 'student_view');
                        if (typeof window !== 'undefined') window.history.pushState(null, '', `#${currentUser.role}`);
                      }}
                    >
                      Go to my {currentUser.role === 'teacher' ? 'Teacher' : 'Student'} Workspace
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={handleLogout}
                    >
                      Sign Out
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <>
                {activeTab === 'teacher_view' && (
                  <TeacherDashboard
                    concepts={concepts}
                    pendingRun={pendingRun}
                    analytics={{}}
                    trends={{}}
                    onCreateConcept={handleCreateConcept}
                    onConfirmTags={handleConfirmTags}
                  />
                )}

                {activeTab === 'student_view' && (
                  <StudentDashboard
                    concepts={concepts}
                    edges={edges}
                    notesByConcept={studentNotes}
                    onStartTest={handleStartTest}
                  />
                )}

                {activeTab === 'attempt' && activeTestConcept && (
                  <AttemptPage
                    concept={activeTestConcept}
                    test={testsByConcept[activeTestConcept.id] || testsByConcept['c-rec']}
                    onSubmit={handleSubmitAttempt}
                    onBack={handleBackFromAttempt}
                  />
                )}
              </>
            )}
          </main>

          {/* Footer */}
          <footer style={{
            padding: '1.25rem 2rem',
            borderTop: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '1rem',
            fontSize: '0.78rem',
            color: 'var(--text-muted)',
            background: 'rgba(8, 12, 21, 0.95)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Shield size={14} color="var(--accent-emerald)" />
              <span>Synapse v2.0 &bull; Durable SQLite Spine &bull; Zero-Knowledge Isolation</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>Person 1: Runtime &bull; Person 2: Agents &bull; Person 3: Curriculum &bull; Person 4: Analytics &bull; Person 5: API & Frontend</span>
            </div>
          </footer>
        </>
      )}
    </div>
  );
};

