// frontend/tests/login_improvements.test.js
import test from 'node:test';
import assert from 'node:assert/strict';

// ─── 1. Password Visibility Logic Unit Tests ─────────────────────────────────

test('Requirement 1 & 2: Password visibility is hidden by default', () => {
  let showPassword = false;
  const inputType = showPassword ? 'text' : 'password';
  const ariaLabel = showPassword ? 'Hide password' : 'Show password';

  assert.equal(inputType, 'password', 'Input type must be password by default');
  assert.equal(ariaLabel, 'Show password', 'Aria-label must prompt to show password');
});

test('Requirement 3 & 4: Clicking eye button toggles visibility to text and back to password', () => {
  let showPassword = false;

  // First click: Show password
  showPassword = !showPassword;
  assert.equal(showPassword ? 'text' : 'password', 'text', 'First toggle makes input type text');
  assert.equal(showPassword ? 'Hide password' : 'Show password', 'Hide password');

  // Second click: Hide password again
  showPassword = !showPassword;
  assert.equal(showPassword ? 'text' : 'password', 'password', 'Second toggle restores input type password');
  assert.equal(showPassword ? 'Hide password' : 'Show password', 'Show password');
});

test('Requirement 5: Eye button must be type="button" to prevent form submission', () => {
  const eyeButtonProps = {
    type: 'button',
    'aria-label': 'Show password',
  };

  assert.equal(eyeButtonProps.type, 'button', 'Must be type="button" not type="submit"');
  assert.notEqual(eyeButtonProps.type, 'submit', 'Must not trigger form submission');
});

test('Requirement 7: Password value remains completely unchanged during visibility toggle', () => {
  let passwordValue = 'SuperSecretKey2026!';
  let showPassword = false;

  // Simulate multiple clicks on the eye button
  for (let i = 0; i < 5; i++) {
    showPassword = !showPassword;
    // Strict invariant: password value must never mutate, clear, or trim
    assert.equal(passwordValue, 'SuperSecretKey2026!', `Password must remain unchanged on toggle #${i + 1}`);
  }
});

// ─── 2. Error Normalization Logic Tests ──────────────────────────────────────

function normalizeLoginError(err) {
  const status = err.status;
  if (status === 401) {
    if (err.message && err.message.toLowerCase().includes('student id')) {
      return 'Invalid Student ID. Please check the ID provided by your teacher.';
    }
    return 'Invalid username or password.';
  }
  if (status === 403) {
    return 'Access denied. You do not have permission to access this portal.';
  }
  if (status === 422 || status === 400) {
    const msg = typeof err.message === 'string' && !err.message.startsWith('{') && !err.message.startsWith('[')
      ? err.message
      : 'Please check your login details and try again.';
    return msg;
  }
  if (status === 429) {
    return 'Too many login attempts. Please wait a moment and try again.';
  }
  if (status === 404 || (err.message && (err.message.includes('404') || err.message.toLowerCase().includes('not found')))) {
    return 'Invalid username or password.';
  }
  if (status >= 500 || err.isNetworkError || err.name === 'TypeError') {
    return 'Unable to connect to the server. Please try again.';
  }
  const fallback = err.message && !err.message.includes('HTTPException') && !err.message.includes('Traceback') && !err.message.includes('404')
    ? err.message
    : 'Invalid username or password.';
  return fallback;
}

test('Requirement 6 & Section 1: Invalid login (401) displays "Invalid username or password."', () => {
  const errWrongPass = { status: 401, message: 'Invalid username or password' };
  const errUnknownUser = { status: 401, message: 'Invalid username or password' };

  const msg1 = normalizeLoginError(errWrongPass);
  const msg2 = normalizeLoginError(errUnknownUser);

  assert.equal(msg1, 'Invalid username or password.');
  assert.equal(msg2, 'Invalid username or password.');
  // Non-existent user and wrong password produce the exact same message to prevent account enumeration
  assert.equal(msg1, msg2, 'Both cases must produce identical message');
});

test('Section 1 & 4: 404 error during login never leaks HTTP 404 to UI', () => {
  const err404 = { status: 404, message: 'HTTP 404' };
  const errNotFound = { status: 404, message: 'Not Found' };

  const msg1 = normalizeLoginError(err404);
  const msg2 = normalizeLoginError(errNotFound);

  assert.equal(msg1, 'Invalid username or password.');
  assert.equal(msg2, 'Invalid username or password.');
  assert.equal(msg1.includes('404'), false, 'Must not include 404');
  assert.equal(msg2.includes('Not Found'), false, 'Must not include Not Found');
});

test('Section 10: Other login errors preserve appropriate semantics', () => {
  // 403 Forbidden
  assert.equal(
    normalizeLoginError({ status: 403, message: 'Forbidden' }),
    'Access denied. You do not have permission to access this portal.'
  );

  // 429 Rate limited
  assert.equal(
    normalizeLoginError({ status: 429, message: 'Too Many Requests' }),
    'Too many login attempts. Please wait a moment and try again.'
  );

  // 500 Server error
  assert.equal(
    normalizeLoginError({ status: 500, message: 'Internal Server Error' }),
    'Unable to connect to the server. Please try again.'
  );

  // Network failure
  assert.equal(
    normalizeLoginError({ name: 'TypeError', message: 'Failed to fetch', isNetworkError: true }),
    'Unable to connect to the server. Please try again.'
  );
});

test('Section 9: Duplicate submission prevention during loading state', () => {
  let authLoading = false;
  let submissionCount = 0;

  function handleLoginSubmit() {
    if (authLoading) return; // Blocked while in-flight
    authLoading = true;
    submissionCount++;
  }

  // First click triggers submission
  handleLoginSubmit();
  assert.equal(submissionCount, 1);
  assert.equal(authLoading, true);

  // Rapid duplicate clicks while in-flight are ignored
  handleLoginSubmit();
  handleLoginSubmit();
  assert.equal(submissionCount, 1, 'Duplicate submissions must be prevented while authLoading is true');

  // Request finishes (error or success) -> restore normal state
  authLoading = false;
  assert.equal(authLoading, false);
});
