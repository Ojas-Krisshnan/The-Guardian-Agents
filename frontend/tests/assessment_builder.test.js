// frontend/tests/assessment_builder.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..', '..');

const teacherDashboardTsx = fs.readFileSync(
  path.join(rootDir, 'frontend', 'src', 'teacher', 'TeacherDashboard.tsx'),
  'utf-8'
);
const clientTs = fs.readFileSync(
  path.join(rootDir, 'frontend', 'src', 'api_client', 'client.ts'),
  'utf-8'
);
const synapseTypesTs = fs.readFileSync(
  path.join(rootDir, 'frontend', 'src', 'types', 'synapse.ts'),
  'utf-8'
);

test('Requirement: Raw JSON textarea is completely removed from Teacher UI', () => {
  assert.equal(
    teacherDashboardTsx.includes('Question Set & Ground-Truth Answers (JSON Array)'),
    false,
    'TeacherDashboard.tsx must NOT contain raw JSON header'
  );
  assert.equal(
    teacherDashboardTsx.includes('asmQuestionsRaw'),
    false,
    'TeacherDashboard.tsx must NOT maintain asmQuestionsRaw state'
  );
  assert.equal(
    teacherDashboardTsx.includes('JSON.parse(asmQuestionsRaw)'),
    false,
    'TeacherDashboard.tsx must NOT parse raw JSON textarea'
  );
});

test('Requirement: Assessment Creation Modal provides segmented tabs for Manual and Upload modes', () => {
  assert.equal(
    teacherDashboardTsx.includes('Create Manually'),
    true,
    'TeacherDashboard.tsx must include "Create Manually" tab'
  );
  assert.equal(
    teacherDashboardTsx.includes('Upload File'),
    true,
    'TeacherDashboard.tsx must include "Upload File" tab'
  );
  assert.equal(
    teacherDashboardTsx.includes("asmMode === 'manual'"),
    true,
    'TeacherDashboard.tsx must support manual mode'
  );
  assert.equal(
    teacherDashboardTsx.includes("asmMode === 'upload'"),
    true,
    'TeacherDashboard.tsx must support upload mode'
  );
});

test('Requirement: Manual Question Builder provides Question, 4 Options (A-D), Correct Answer dropdown, and Concept', () => {
  // Check question text field
  assert.equal(
    teacherDashboardTsx.includes('Question: *'),
    true,
    'Must have Question: * input label'
  );

  // Check 4 options
  assert.equal(
    teacherDashboardTsx.includes("['A', 'B', 'C', 'D']"),
    true,
    'Must map across options A, B, C, D'
  );
  assert.equal(
    teacherDashboardTsx.includes('Option {letter}: *'),
    true,
    'Must render Option {letter}: * label for each option'
  );

  // Check Correct Answer dropdown
  assert.equal(
    teacherDashboardTsx.includes('Correct Answer: *'),
    true,
    'Must have Correct Answer: * dropdown label'
  );
  assert.equal(
    teacherDashboardTsx.includes('handleCorrectAnswerChange'),
    true,
    'Must have handleCorrectAnswerChange handler'
  );

  // Check Concept / Topic
  assert.equal(
    teacherDashboardTsx.includes('Concept / Topic:'),
    true,
    'Must have Concept / Topic: field'
  );
});

test('Requirement: Question card operations (Add, Remove, Clear, Move Up/Down)', () => {
  assert.equal(
    teacherDashboardTsx.includes('handleAddQuestion'),
    true,
    'Must have handleAddQuestion handler'
  );
  assert.equal(
    teacherDashboardTsx.includes('handleRemoveQuestion'),
    true,
    'Must have handleRemoveQuestion handler'
  );
  assert.equal(
    teacherDashboardTsx.includes('handleClearQuestion'),
    true,
    'Must have handleClearQuestion handler'
  );
  assert.equal(
    teacherDashboardTsx.includes('handleMoveQuestion'),
    true,
    'Must have handleMoveQuestion handler'
  );
});

test('Requirement: File Upload area supports PDF, DOC, and DOCX formats with preview and review', () => {
  assert.equal(
    teacherDashboardTsx.includes('Upload Questions from File'),
    true,
    'Must contain Upload Questions from File title'
  );
  assert.equal(
    teacherDashboardTsx.includes('Supported formats: PDF, DOC, DOCX'),
    true,
    'Must declare supported formats PDF, DOC, DOCX'
  );
  assert.equal(
    teacherDashboardTsx.includes('.pdf,.docx,.doc'),
    true,
    'Input accept attribute must specify .pdf, .docx, .doc'
  );
  assert.equal(
    teacherDashboardTsx.includes('Choose File'),
    true,
    'Must have Choose File button'
  );
  assert.equal(
    teacherDashboardTsx.includes('handleFileUpload'),
    true,
    'Must have handleFileUpload handler'
  );
  assert.equal(
    teacherDashboardTsx.includes('uploadProgressText'),
    true,
    'Must display upload progress indicator'
  );
});

test('Requirement: API Client and Types support document extraction', () => {
  assert.equal(
    clientTs.includes('extractAssessmentDocument'),
    true,
    'client.ts must define extractAssessmentDocument'
  );
  assert.equal(
    synapseTypesTs.includes('ExtractedQuestionItem'),
    true,
    'synapse.ts must export ExtractedQuestionItem'
  );
  assert.equal(
    synapseTypesTs.includes('ExtractDocumentResponse'),
    true,
    'synapse.ts must export ExtractDocumentResponse'
  );
});
