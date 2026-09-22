// frontend/tests/student_classroom_removal.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..', '..');

// Read source files directly to test static code invariants
const appTsx = fs.readFileSync(path.join(rootDir, 'frontend', 'src', 'App.tsx'), 'utf-8');
const studentDashboardTsx = fs.readFileSync(path.join(rootDir, 'frontend', 'src', 'student', 'StudentDashboard.tsx'), 'utf-8');

test('Requirement 1 & 2: Student Login Form does NOT contain Classroom ID selection or input', () => {
  // Must not have studentAuthMethod selector or Classroom ID buttons in student login
  assert.equal(appTsx.includes('setStudentAuthMethod'), false, 'App.tsx must not contain setStudentAuthMethod');
  assert.equal(appTsx.includes('studentAuthMethod'), false, 'App.tsx must not contain studentAuthMethod state');
  assert.equal(appTsx.includes('Enter Classroom'), false, 'App.tsx must not contain "Enter Classroom" button');
  assert.equal(appTsx.includes('Classroom Student ID'), false, 'App.tsx must not contain "Classroom Student ID"');
  assert.equal(appTsx.includes('Enter your STU- ID'), false, 'App.tsx must not contain "Enter your STU- ID" placeholder');
});

test('Requirement 2: Student Login renders clean Username/Email & Password form', () => {
  // Must render standard fields
  assert.equal(appTsx.includes('Sign In as Student'), true, 'App.tsx must contain "Sign In as Student" button');
  assert.equal(appTsx.includes('studentUserInput'), true, 'App.tsx must use studentUserInput for login');
  assert.equal(appTsx.includes('studentPassInput'), true, 'App.tsx must use studentPassInput for password');
  assert.equal(appTsx.includes('showStudentPassword'), true, 'App.tsx must maintain password visibility eye toggle');
});

test('Requirement 3 & 4: Student Portal does NOT contain obsolete classroom-join UI', () => {
  const forbiddenPhrases = [
    'Enter Classroom ID',
    'Join Classroom',
    'Join using Classroom ID',
    'Enter class code',
    'Join class',
    'Join Class',
    'Classroom Code',
  ];

  for (const phrase of forbiddenPhrases) {
    assert.equal(
      studentDashboardTsx.toLowerCase().includes(phrase.toLowerCase()),
      false,
      `StudentDashboard.tsx must NOT contain '${phrase}'`
    );
  }
});

test('Requirement 5: Teacher Connection section uses authoritative Teacher Connection Code terminology', () => {
  assert.equal(
    studentDashboardTsx.includes('Teacher Connection'),
    true,
    'StudentDashboard.tsx must feature "Teacher Connection" header'
  );
  assert.equal(
    studentDashboardTsx.includes('Teacher Connection Code'),
    true,
    'StudentDashboard.tsx must prompt for "Teacher Connection Code"'
  );
  assert.equal(
    studentDashboardTsx.includes('Connect to Teacher'),
    true,
    'StudentDashboard.tsx must have "Connect to Teacher" button'
  );
  assert.equal(
    studentDashboardTsx.includes('placeholder="SYN-XXXXXX"'),
    true,
    'StudentDashboard.tsx must use 6-char SYN- code format placeholder'
  );
});

test('Requirement 6: Teacher functionality preserves classrooms and rosters', () => {
  const teacherDashboardTsx = fs.readFileSync(path.join(rootDir, 'frontend', 'src', 'teacher', 'TeacherDashboard.tsx'), 'utf-8');
  assert.equal(teacherDashboardTsx.includes('ClassroomResponse'), true, 'Teacher dashboard must preserve ClassroomResponse');
  assert.equal(teacherDashboardTsx.includes('handleCreateClassroom'), true, 'Teacher dashboard must preserve classroom creation');
  assert.equal(teacherDashboardTsx.includes('listClassrooms'), true, 'Teacher dashboard must preserve listing classrooms');
  assert.equal(teacherDashboardTsx.includes('listClassroomStudents'), true, 'Teacher dashboard must preserve student roster');
});
