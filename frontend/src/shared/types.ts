export type UserRole = 'teacher' | 'student';

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: UserRole;
}

export type RunState =
  | 'drafting'
  | 'gating'
  | 'probing'
  | 'awaiting_expert'
  | 'complete'
  | 'failed';

export interface Run {
  id: string;
  domain: string;
  state: RunState;
  created_at: number;
  updated_at: number;
  meta: Record<string, any>;
}

export interface Version {
  seq: number;
  kind: string;
  produced_by: string;
  payload: Record<string, any>;
  created_at: number;
}

export interface Question {
  id: string;
  run_id: string;
  question: string;
  context: Record<string, any>;
  asked_at: number;
  timeout_at: number;
  answered_at: number | null;
  answer: string | null;
  is_answered: boolean;
  is_expired: boolean;
}

export interface ApiError {
  detail: string;
}
