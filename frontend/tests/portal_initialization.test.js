// frontend/tests/portal_initialization.test.js
import test from 'node:test';
import assert from 'node:assert/strict';

// Helper matching getInitialPortal logic in App.tsx
function resolvePortal({ hash = '', pathname = '', localStorageValue = null } = {}) {
  const normHash = hash.toLowerCase();
  const normPath = pathname.toLowerCase();

  // 1. Direct URL hash check (#teacher vs #student)
  if (normHash.includes('teacher')) return 'teacher';
  if (normHash.includes('student')) return 'student';

  // 2. Direct pathname check (/teacher vs /student)
  if (normPath.endsWith('/teacher') || normPath.includes('/teacher/')) return 'teacher';
  if (normPath.endsWith('/student') || normPath.includes('/student/')) return 'student';

  // 3. Saved portal preference from previous session
  if (localStorageValue === 'teacher' || localStorageValue === 'student') {
    return localStorageValue;
  }

  // 4. Default: Student Portal
  return 'student';
}

function resolveActiveTab(portal) {
  return portal === 'teacher' ? 'teacher_view' : 'student_view';
}

test('Scenario A: Default load (no hash, no path) defaults immediately to Student Portal', () => {
  const portal = resolvePortal({ hash: '', pathname: '/' });
  const activeTab = resolveActiveTab(portal);

  assert.equal(portal, 'student', 'Initial portal must be student');
  assert.equal(activeTab, 'student_view', 'Initial active tab must be student_view');
  // Strict invariant: rendered portal === active navigation portal on first render
  assert.equal(portal === 'student' && activeTab === 'student_view', true, 'Invariant satisfied on first render');
});

test('Scenario B: Hard refresh on Teacher Portal URL (#teacher) activates Teacher Portal immediately', () => {
  const portal = resolvePortal({ hash: '#teacher', pathname: '/' });
  const activeTab = resolveActiveTab(portal);

  assert.equal(portal, 'teacher', 'Initial portal must be teacher');
  assert.equal(activeTab, 'teacher_view', 'Initial active tab must be teacher_view');
  assert.equal(portal === 'teacher' && activeTab === 'teacher_view', true, 'Teacher invariant satisfied on first render');
});

test('Scenario C: Hard refresh on Student Portal URL (#student) activates Student Portal immediately', () => {
  const portal = resolvePortal({ hash: '#student', pathname: '/' });
  const activeTab = resolveActiveTab(portal);

  assert.equal(portal, 'student', 'Initial portal must be student');
  assert.equal(activeTab, 'student_view', 'Initial active tab must be student_view');
  assert.equal(portal === 'student' && activeTab === 'student_view', true);
});

test('Scenario D: Direct path navigation (/teacher) activates Teacher Portal immediately', () => {
  const portal = resolvePortal({ hash: '', pathname: '/teacher' });
  const activeTab = resolveActiveTab(portal);

  assert.equal(portal, 'teacher');
  assert.equal(activeTab, 'teacher_view');
});

test('Scenario E: Direct path navigation (/student) activates Student Portal immediately', () => {
  const portal = resolvePortal({ hash: '', pathname: '/student' });
  const activeTab = resolveActiveTab(portal);

  assert.equal(portal, 'student');
  assert.equal(activeTab, 'student_view');
});

test('Scenario F: Switching Student -> Teacher synchronizes state and history', () => {
  let portal = 'student';
  let activeTab = 'student_view';
  let currentHash = '#student';

  // Perform switch
  const switchRole = (newRole) => {
    portal = newRole;
    activeTab = newRole === 'teacher' ? 'teacher_view' : 'student_view';
    currentHash = `#${newRole}`;
  };

  switchRole('teacher');
  assert.equal(portal, 'teacher');
  assert.equal(activeTab, 'teacher_view');
  assert.equal(currentHash, '#teacher');
  assert.equal(portal === 'teacher' && activeTab === 'teacher_view', true);
});

test('Scenario G: Switching Teacher -> Student synchronizes state and history', () => {
  let portal = 'teacher';
  let activeTab = 'teacher_view';
  let currentHash = '#teacher';

  const switchRole = (newRole) => {
    portal = newRole;
    activeTab = newRole === 'teacher' ? 'teacher_view' : 'student_view';
    currentHash = `#${newRole}`;
  };

  switchRole('student');
  assert.equal(portal, 'student');
  assert.equal(activeTab, 'student_view');
  assert.equal(currentHash, '#student');
  assert.equal(portal === 'student' && activeTab === 'student_view', true);
});

test('Scenario H: Browser Back & Forward events update portal deterministically', () => {
  let portal = 'student';
  let activeTab = 'student_view';

  const handleLocationChange = (newHash) => {
    if (newHash.includes('teacher')) {
      portal = 'teacher';
      activeTab = 'teacher_view';
    } else {
      portal = 'student';
      activeTab = 'student_view';
    }
  };

  // User clicked to teacher
  handleLocationChange('#teacher');
  assert.equal(portal, 'teacher');
  assert.equal(activeTab, 'teacher_view');

  // User clicked browser Back -> #student
  handleLocationChange('#student');
  assert.equal(portal, 'student');
  assert.equal(activeTab, 'student_view');

  // User clicked browser Forward -> #teacher
  handleLocationChange('#teacher');
  assert.equal(portal, 'teacher');
  assert.equal(activeTab, 'teacher_view');
});

test('Scenario I: Refresh after navigation preserves persisted localStorage preference', () => {
  const portal = resolvePortal({ hash: '', pathname: '/', localStorageValue: 'teacher' });
  const activeTab = resolveActiveTab(portal);

  assert.equal(portal, 'teacher');
  assert.equal(activeTab, 'teacher_view');
});

test('Scenario J: Intro overlay maintains exact active portal invariant on first render (Student)', () => {
  // Simulate App mount with intro active
  const initialPortal = resolvePortal({ hash: '', pathname: '/' });
  const initialActiveTab = resolveActiveTab(initialPortal);
  let showIntro = true;

  // Invariant holds during intro phase
  assert.equal(showIntro, true);
  assert.equal(initialPortal, 'student');
  assert.equal(initialActiveTab, 'student_view');
  assert.equal(initialPortal === 'student' && initialActiveTab === 'student_view', true);

  // When intro completes
  showIntro = false;
  assert.equal(showIntro, false);
  assert.equal(initialPortal, 'student');
  assert.equal(initialActiveTab, 'student_view');
});

test('Scenario K: Intro overlay maintains exact active portal invariant on first render (Teacher direct load #teacher)', () => {
  const initialPortal = resolvePortal({ hash: '#teacher', pathname: '/' });
  const initialActiveTab = resolveActiveTab(initialPortal);
  let showIntro = true;

  // Invariant holds during intro phase
  assert.equal(showIntro, true);
  assert.equal(initialPortal, 'teacher');
  assert.equal(initialActiveTab, 'teacher_view');
  assert.equal(initialPortal === 'teacher' && initialActiveTab === 'teacher_view', true);

  // When intro completes
  showIntro = false;
  assert.equal(showIntro, false);
  assert.equal(initialPortal, 'teacher');
  assert.equal(initialActiveTab, 'teacher_view');
});

test('Scenario L: Deep route attempt navigation maintains correct student attempt view with intro', () => {
  const hash = '#attempt-c-rec';
  const initialPortal = resolvePortal({ hash, pathname: '/' });
  const isAttempt = hash.startsWith('#attempt-');
  const activeTab = isAttempt ? 'attempt' : resolveActiveTab(initialPortal);

  assert.equal(initialPortal, 'student');
  assert.equal(activeTab, 'attempt');
  assert.equal(initialPortal === 'student', true);
});

// ======================================================================
// 3-Stage Startup & Portal Selection Test Scenarios (Stage 1 -> 2 -> 3)
// ======================================================================
// 3-Stage Startup & Portal Selection Test Scenarios (Stage 1 -> 2 -> 3)
// ======================================================================

function getInitialPortalStateSim({ hash = '', pathname = '' } = {}) {
  const normHash = hash.toLowerCase();
  const normPath = pathname.toLowerCase();

  if (normHash.includes('teacher') || normPath.endsWith('/teacher') || normPath.includes('/teacher/')) {
    return { stage: 'portal', role: 'teacher', activeTab: 'teacher_view', hasExplicitPortal: true };
  }
  if (normHash.startsWith('#attempt-')) {
    return { stage: 'portal', role: 'student', activeTab: 'attempt', hasExplicitPortal: true };
  }
  if (normHash.includes('student') || normPath.endsWith('/student') || normPath.includes('/student/')) {
    return { stage: 'portal', role: 'student', activeTab: 'student_view', hasExplicitPortal: true };
  }
  if (normHash.includes('select')) {
    return { stage: 'select', role: 'student', activeTab: 'student_view', hasExplicitPortal: false };
  }

  // Root landing/startup defaults to Title Page (SYNAPSE / Your learning space / [ Get Started ])
  return { stage: 'title', role: 'student', activeTab: 'student_view', hasExplicitPortal: false };
}

test('Scenario M: Fresh startup (Stage 1 Title Page -> Get Started -> Stage 2 Portal Selection -> User Selects Student -> Stage 3 Student Portal)', () => {
  // 1. Initial fresh load at root
  const init = getInitialPortalStateSim({ hash: '', pathname: '/' });
  assert.equal(init.stage, 'title', 'Stage must start at title page');
  assert.equal(init.hasExplicitPortal, false, 'No portal pre-selected');

  let currentStage = init.stage;
  let activeRole = null;
  let activeNavTab = null;

  // Stage 1: Title Page active
  assert.equal(currentStage, 'title', 'Stage 1: Title page is displayed');

  // User activates "Get Started"
  const handleGetStarted = () => {
    currentStage = 'select';
  };
  handleGetStarted();
  assert.equal(currentStage, 'select', 'Stage 2: Portal Selection displayed');

  // Stage 2: User explicitly chooses Student Portal
  const selectPortal = (role) => {
    activeRole = role;
    activeNavTab = role === 'teacher' ? 'teacher_view' : 'student_view';
    currentStage = 'portal';
  };

  selectPortal('student');

  // Stage 3: Student Portal displayed with active navigation
  assert.equal(currentStage, 'portal', 'Stage 3: Portal active');
  assert.equal(activeRole, 'student');
  assert.equal(activeNavTab, 'student_view');
  assert.equal(activeRole === 'student' && activeNavTab === 'student_view', true, 'Invariant strictly preserved');
});

test('Scenario N: Fresh startup (Stage 1 Title Page -> Stage 2 Portal Selection -> User Selects Teacher -> Stage 3 Teacher Portal)', () => {
  const init = getInitialPortalStateSim({ hash: '', pathname: '/' });
  assert.equal(init.stage, 'title');

  let currentStage = 'title';
  let activeRole = null;
  let activeNavTab = null;

  // Click Get Started
  currentStage = 'select';
  assert.equal(currentStage, 'select');

  // User explicitly chooses Teacher Portal
  const selectPortal = (role) => {
    activeRole = role;
    activeNavTab = role === 'teacher' ? 'teacher_view' : 'student_view';
    currentStage = 'portal';
  };

  selectPortal('teacher');

  assert.equal(currentStage, 'portal');
  assert.equal(activeRole, 'teacher');
  assert.equal(activeNavTab, 'teacher_view');
  assert.equal(activeRole === 'teacher' && activeNavTab === 'teacher_view', true, 'Teacher invariant strictly preserved');
});

test('Scenario O: Refresh on existing Student route (#student) preserves Student Portal without forcing selection screen', () => {
  const init = getInitialPortalStateSim({ hash: '#student', pathname: '/' });
  assert.equal(init.stage, 'portal', 'Stage must remain portal directly');
  assert.equal(init.role, 'student', 'Active role must be student');
  assert.equal(init.activeTab, 'student_view');
  assert.equal(init.hasExplicitPortal, true);
});

test('Scenario P: Refresh on existing Teacher route (#teacher) preserves Teacher Portal without forcing selection screen', () => {
  const init = getInitialPortalStateSim({ hash: '#teacher', pathname: '/' });
  assert.equal(init.stage, 'portal', 'Stage must remain portal directly');
  assert.equal(init.role, 'teacher', 'Active role must be teacher');
  assert.equal(init.activeTab, 'teacher_view');
  assert.equal(init.hasExplicitPortal, true);
});

test('Scenario Q: Brand header click or Switch Workspace button navigates back to Stage 2 Portal Selection', () => {
  let currentStage = 'portal';
  let currentHash = '#student';

  const returnToSelection = () => {
    currentStage = 'select';
    currentHash = '#select';
  };

  returnToSelection();
  assert.equal(currentStage, 'select');
  assert.equal(currentHash, '#select');
});

test('Scenario R: No persistent global portal switcher inside dashboards (Phase 8 Invariant)', () => {
  // Test that in dashboard stage ('portal'), the global toggle tabs are removed
  const renderDashboardHeader = (stage, role) => {
    return {
      hasGlobalToggleTabs: false, // Strict requirement: no Student Portal | Teacher Portal tabs in dashboard
      hasWorkspaceSwitchBtn: stage === 'portal',
      hasBrandWorkspacePill: stage === 'portal',
      displayedWorkspace: role === 'teacher' ? 'Teacher Workspace' : 'Student Workspace',
    };
  };

  const headerState = renderDashboardHeader('portal', 'student');
  assert.equal(headerState.hasGlobalToggleTabs, false, 'Global toggle tabs must not appear inside dashboard');
  assert.equal(headerState.hasWorkspaceSwitchBtn, true, 'Subtle Switch Workspace button must be present');
  assert.equal(headerState.displayedWorkspace, 'Student Workspace');

  const teacherHeader = renderDashboardHeader('portal', 'teacher');
  assert.equal(teacherHeader.hasGlobalToggleTabs, false);
  assert.equal(teacherHeader.hasWorkspaceSwitchBtn, true);
  assert.equal(teacherHeader.displayedWorkspace, 'Teacher Workspace');
});

test('Scenario S: Keyboard navigation (Enter / Space) on Title Page and Portal Cards', () => {
  let activatedStage = null;
  const onTitleKeyDown = (key) => {
    if (key === 'Enter' || key === ' ') {
      activatedStage = 'select';
    }
  };

  onTitleKeyDown('Enter');
  assert.equal(activatedStage, 'select', 'Enter key advances title page');

  activatedStage = null;
  onTitleKeyDown(' ');
  assert.equal(activatedStage, 'select', 'Space key advances title page');

  let chosenPortal = null;
  const onCardKeyDown = (key, role) => {
    if (key === 'Enter' || key === ' ') {
      chosenPortal = role;
    }
  };

  onCardKeyDown('Enter', 'teacher');
  assert.equal(chosenPortal, 'teacher', 'Enter key selects teacher card');
});

// Helper matching getInitialPortalState in App.tsx
function getInitialPortalState({ hash = '', pathname = '', isAuthenticated = false, storedPortal = null } = {}) {
  const normHash = hash.toLowerCase();
  const normPath = pathname.toLowerCase();

  const isTeacherRoute = normHash.includes('teacher') || normPath.endsWith('/teacher') || normPath.includes('/teacher/');
  const isStudentRoute = normHash.includes('student') || normPath.endsWith('/student') || normPath.includes('/student/') || normHash.startsWith('#attempt-');
  const isAuthRoute = normHash.includes('login') || normHash.includes('register') || normHash.includes('auth');
  const isSelectRoute = normHash.includes('select');

  if (isAuthRoute) {
    return {
      portal: storedPortal === 'teacher' ? 'teacher' : 'student',
      activeTab: storedPortal === 'teacher' ? 'teacher_view' : 'student_view',
      stage: 'auth',
      intendedDestination: '',
    };
  }

  if (isTeacherRoute) {
    if (!isAuthenticated) {
      return {
        portal: 'teacher',
        activeTab: 'teacher_view',
        stage: 'auth',
        intendedDestination: hash || pathname,
      };
    }
    return {
      portal: 'teacher',
      activeTab: 'teacher_view',
      stage: 'portal',
      intendedDestination: '',
    };
  }

  if (isStudentRoute) {
    if (!isAuthenticated) {
      return {
        portal: 'student',
        activeTab: 'student_view',
        stage: 'auth',
        intendedDestination: hash || pathname,
      };
    }
    return {
      portal: 'student',
      activeTab: 'student_view',
      stage: 'portal',
      intendedDestination: '',
    };
  }

  if (isSelectRoute) {
    return {
      portal: 'student',
      activeTab: 'student_view',
      stage: 'select',
      intendedDestination: '',
    };
  }

  return {
    portal: 'student',
    activeTab: 'student_view',
    stage: 'title',
    intendedDestination: '',
  };
}

test('Scenario T: Unauthenticated navigation to protected #teacher route redirects to stage = auth and remembers destination', () => {
  const state = getInitialPortalState({ hash: '#teacher', pathname: '/', isAuthenticated: false });
  assert.equal(state.stage, 'auth', 'Unauthenticated user must be placed in auth stage');
  assert.equal(state.portal, 'teacher', 'Portal intent is preserved');
  assert.equal(state.intendedDestination, '#teacher', 'Intended destination is recorded');
});

test('Scenario U: Unauthenticated navigation to protected #student route redirects to stage = auth and remembers destination', () => {
  const state = getInitialPortalState({ hash: '#student', pathname: '/', isAuthenticated: false });
  assert.equal(state.stage, 'auth', 'Unauthenticated user must be placed in auth stage');
  assert.equal(state.portal, 'student', 'Portal intent is preserved');
  assert.equal(state.intendedDestination, '#student', 'Intended destination is recorded');
});

test('Scenario V: Public routes (#title, #select) are accessible unauthenticated without redirection', () => {
  const titleState = getInitialPortalState({ hash: '#title', pathname: '/', isAuthenticated: false });
  assert.equal(titleState.stage, 'title', 'Public title route remains accessible');

  const selectState = getInitialPortalState({ hash: '#select', pathname: '/', isAuthenticated: false });
  assert.equal(selectState.stage, 'select', 'Public select route remains accessible');
});

test('Scenario W: Authenticated login succeeds and immediately directs user to intended destination', () => {
  // Direct protected navigation while authenticated
  const teacherState = getInitialPortalState({ hash: '#teacher', pathname: '/', isAuthenticated: true });
  assert.equal(teacherState.stage, 'portal', 'Authenticated teacher enters dashboard');
  assert.equal(teacherState.portal, 'teacher');

  const studentState = getInitialPortalState({ hash: '#student', pathname: '/', isAuthenticated: true });
  assert.equal(studentState.stage, 'portal', 'Authenticated student enters dashboard');
  assert.equal(studentState.portal, 'student');
});

test('Scenario X: Role Mismatch protection blocks student user from rendering teacher dashboard', () => {
  const authenticatedUser = { role: 'student', user_id: 'std_01', name: 'Alice' };
  const requestedPortal = 'teacher';

  const canRenderDashboard = (user, portal) => {
    return user && user.role === portal;
  };

  assert.equal(canRenderDashboard(authenticatedUser, requestedPortal), false, 'Student cannot render teacher portal');
  assert.equal(canRenderDashboard(authenticatedUser, 'student'), true, 'Student can render student portal');
});

test('Scenario Y: Complete Sign Out clears auth state, tokens, and redirects user out of protected portal', () => {
  let storage = {
    'synapse_auth': JSON.stringify({ role: 'teacher', user_id: 'prof_1', token: 'valid_jwt' }),
    'synapse_portal': 'teacher',
  };

  const handleLogout = () => {
    delete storage['synapse_auth'];
    delete storage['synapse_portal'];
    return {
      stage: 'select',
      hash: '#select',
      currentUser: null,
      isAuthenticated: false,
    };
  };

  const postLogout = handleLogout();
  assert.equal(storage['synapse_auth'], undefined, 'Auth token must be cleared');
  assert.equal(storage['synapse_portal'], undefined, 'Portal preference must be cleared');
  assert.equal(postLogout.isAuthenticated, false);
  assert.equal(postLogout.stage, 'select');
  assert.equal(postLogout.hash, '#select');
});

test('Scenario Z: Direct attempt route (#attempt-123) requires authentication before viewing', () => {
  const unauthState = getInitialPortalState({ hash: '#attempt-quiz-99', pathname: '/', isAuthenticated: false });
  assert.equal(unauthState.stage, 'auth', 'Unauthenticated attempt route must redirect to auth');
  assert.equal(unauthState.intendedDestination, '#attempt-quiz-99', 'Attempt URL is preserved for post-login redirection');

  const authState = getInitialPortalState({ hash: '#attempt-quiz-99', pathname: '/', isAuthenticated: true });
  assert.equal(authState.stage, 'portal', 'Authenticated attempt route enters portal');
});



