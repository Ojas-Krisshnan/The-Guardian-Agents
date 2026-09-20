// frontend/src/api_client/client.ts
import type {
  CreateConceptRequest,
  CreateConceptResponse,
  PendingTagsResponse,
  ConfirmTagsRequest,
  ConfirmTagsResponse,
  TeacherAnalyticsResponse,
  TeacherTrendsResponse,
  SubmitAttemptRequest,
  SubmitAttemptResponse,
  StudentNotesResponse,
  StudentGraphResponse,
  RunStatusResponse,
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  UserResponse,
  CreateClassroomRequest,
  ClassroomResponse,
  GenerateStudentsRequest,
  GenerateStudentsResponse,
  ClassroomStudentItem,
  CreateAssessmentRequest,
  AssessmentResponse,
  UploadQuestionsRequest,
  UploadAnswersRequest,
  MapConceptsRequest,
  AssessmentQuestionResponse,
  TakeAssessmentResponse,
  StudentAttemptSubmitRequest,
  StudentAttemptResponse,
  StudentAnalyticsResponse,
  ClassroomAnalyticsResponse,
  TeacherInsightResponse,
  TeacherConnectionCodeResponse,
  ConnectedStudentSummary,
  ConnectedStudentPerformanceResponse,
  StudentConnectRequest,
  StudentConnectResponse,
  StudentTeacherListResponse,
} from '../types/synapse';

const API_BASE = '';

export class ApiClient {
  private token: string | null = null;
  private role: 'teacher' | 'student' | null = null;
  private userId: string | null = null;
  private userName: string | null = null;

  constructor() {
    // Try to load saved auth session
    if (typeof localStorage !== 'undefined') {
      try {
        const saved = localStorage.getItem('synapse_auth');
        if (saved) {
          const parsed = JSON.parse(saved);
          this.token = parsed.token || null;
          this.role = parsed.role || null;
          this.userId = parsed.userId || null;
          this.userName = parsed.userName || parsed.userId || null;
        }
      } catch {}
    }
  }

  isAuthenticated(): boolean {
    return Boolean(this.token);
  }

  setAuth(role: 'teacher' | 'student', userId: string, token: string, userName?: string) {
    this.role = role;
    this.userId = userId;
    this.token = token;
    this.userName = userName || userId;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('synapse_auth', JSON.stringify({ role, userId, token, userName: this.userName }));
      localStorage.setItem('synapse_portal', role);
    }
  }

  clearAuth() {
    this.token = null;
    this.role = null;
    this.userId = null;
    this.userName = null;
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('synapse_auth');
      localStorage.removeItem('synapse_portal');
    }
  }

  getAuth() {
    return {
      role: this.role,
      userId: this.userId,
      token: this.token,
      userName: this.userName,
      isAuthenticated: Boolean(this.token),
    };
  }

  async validateSession(): Promise<UserResponse | null> {
    if (!this.token) return null;
    try {
      const me = await this.getMe();
      if (me && me.role) {
        this.role = me.role as 'teacher' | 'student';
        this.userId = me.id;
        this.userName = me.name || me.username || me.id;
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem('synapse_auth', JSON.stringify({
            role: this.role,
            userId: this.userId,
            token: this.token,
            userName: this.userName,
          }));
        }
        return me;
      }
      this.clearAuth();
      return null;
    } catch {
      this.clearAuth();
      return null;
    }
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers || {});
    headers.set('Content-Type', 'application/json');
    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`);
    }

    try {
      const resp = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
      });

      if (!resp.ok) {
        const errText = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${errText}`);
      }

      return (await resp.json()) as T;
    } catch (err: any) {
      console.warn(`API request to ${path} failed: ${err.message}`);
      throw err;
    }
  }

  // ─── Authentication ───────────────────────────────────────────────────────
  async login(req: LoginRequest): Promise<AuthResponse> {
    const resp = await this.request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(req),
    });
    this.setAuth(resp.user.role as 'teacher' | 'student', resp.user.id, resp.token, resp.user.name);
    return resp;
  }

  async register(req: RegisterRequest): Promise<AuthResponse> {
    const resp = await this.request<AuthResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(req),
    });
    this.setAuth(resp.user.role as 'teacher' | 'student', resp.user.id, resp.token, resp.user.name);
    return resp;
  }

  async getMe(): Promise<UserResponse> {
    return this.request<UserResponse>('/auth/me');
  }

  // ─── Classroom Management (Teacher) ──────────────────────────────────────
  async createClassroom(req: CreateClassroomRequest): Promise<ClassroomResponse> {
    return this.request<ClassroomResponse>('/teacher/classrooms', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  }

  async listClassrooms(): Promise<ClassroomResponse[]> {
    return this.request<ClassroomResponse[]>('/teacher/classrooms');
  }

  async getClassroom(classId: string): Promise<ClassroomResponse> {
    return this.request<ClassroomResponse>(`/teacher/classrooms/${classId}`);
  }

  async generateStudents(classId: string, count: number): Promise<GenerateStudentsResponse> {
    return this.request<GenerateStudentsResponse>(`/teacher/classrooms/${classId}/students/generate`, {
      method: 'POST',
      body: JSON.stringify({ count }),
    });
  }

  async listClassroomStudents(classId: string): Promise<ClassroomStudentItem[]> {
    return this.request<ClassroomStudentItem[]>(`/teacher/classrooms/${classId}/students`);
  }

  // ─── Assessment Management (Teacher) ─────────────────────────────────────
  async createAssessment(classId: string, req: CreateAssessmentRequest): Promise<AssessmentResponse> {
    return this.request<AssessmentResponse>(`/teacher/classrooms/${classId}/assessments`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
  }

  async listClassroomAssessments(classId: string): Promise<AssessmentResponse[]> {
    return this.request<AssessmentResponse[]>(`/teacher/classrooms/${classId}/assessments`);
  }

  async getAssessment(assessmentId: string): Promise<{ assessment: AssessmentResponse; questions: AssessmentQuestionResponse[] }> {
    return this.request<{ assessment: AssessmentResponse; questions: AssessmentQuestionResponse[] }>(`/teacher/assessments/${assessmentId}`);
  }

  async uploadQuestions(assessmentId: string, req: UploadQuestionsRequest): Promise<AssessmentQuestionResponse[]> {
    return this.request<AssessmentQuestionResponse[]>(`/teacher/assessments/${assessmentId}/questions/upload`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
  }

  async uploadAnswers(assessmentId: string, req: UploadAnswersRequest): Promise<AssessmentQuestionResponse[]> {
    return this.request<AssessmentQuestionResponse[]>(`/teacher/assessments/${assessmentId}/answers/upload`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
  }

  async mapConcepts(assessmentId: string, req: MapConceptsRequest): Promise<AssessmentQuestionResponse[]> {
    return this.request<AssessmentQuestionResponse[]>(`/teacher/assessments/${assessmentId}/map-concepts`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
  }

  async publishAssessment(assessmentId: string): Promise<AssessmentResponse> {
    return this.request<AssessmentResponse>(`/teacher/assessments/${assessmentId}/publish`, {
      method: 'POST',
    });
  }

  async getClassroomAnalytics(classId: string): Promise<ClassroomAnalyticsResponse> {
    return this.request<ClassroomAnalyticsResponse>(`/teacher/classrooms/${classId}/analytics`);
  }

  async getClassroomInsights(classId: string): Promise<TeacherInsightResponse[]> {
    return this.request<TeacherInsightResponse[]>(`/teacher/classrooms/${classId}/insights`);
  }

  // ─── Teacher ↔ Student Connection Operations ─────────────────────────────
  async getTeacherConnectionCode(): Promise<TeacherConnectionCodeResponse> {
    return this.request<TeacherConnectionCodeResponse>('/teacher/connection-code');
  }

  async getTeacherConnectedStudents(): Promise<ConnectedStudentSummary[]> {
    return this.request<ConnectedStudentSummary[]>('/teacher/students');
  }

  async getTeacherStudentPerformance(studentId: string): Promise<ConnectedStudentPerformanceResponse> {
    return this.request<ConnectedStudentPerformanceResponse>(`/teacher/students/${studentId}/performance`);
  }

  // ─── Student Operations ──────────────────────────────────────────────────
  async getStudentClassrooms(): Promise<any[]> {
    return this.request<any[]>('/student/classrooms');
  }

  async getStudentAssessments(): Promise<AssessmentResponse[]> {
    return this.request<AssessmentResponse[]>('/student/assessments');
  }

  async getStudentAssessment(assessmentId: string): Promise<TakeAssessmentResponse> {
    return this.request<TakeAssessmentResponse>(`/student/assessments/${assessmentId}`);
  }

  async submitAssessmentAttempt(assessmentId: string, req: StudentAttemptSubmitRequest): Promise<StudentAttemptResponse> {
    return this.request<StudentAttemptResponse>(`/student/assessments/${assessmentId}/attempt`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
  }

  async listStudentAttempts(): Promise<any[]> {
    return this.request<any[]>('/student/attempts');
  }

  async getStudentAttempt(attemptId: string): Promise<any> {
    return this.request<any>(`/student/attempts/${attemptId}`);
  }

  async getStudentAnalytics(): Promise<StudentAnalyticsResponse> {
    return this.request<StudentAnalyticsResponse>('/student/analytics');
  }

  async getAllStudentNotes(): Promise<StudentNotesResponse> {
    return this.request<StudentNotesResponse>('/student/notes');
  }

  async connectStudentToTeacher(code: string): Promise<StudentConnectResponse> {
    return this.request<StudentConnectResponse>('/student/connect', {
      method: 'POST',
      body: JSON.stringify({ code }),
    });
  }

  async getStudentConnectedTeachers(): Promise<StudentTeacherListResponse> {
    return this.request<StudentTeacherListResponse>('/student/teacher');
  }

  // ─── Legacy / Backbone Endpoints ─────────────────────────────────────────
  async createConcept(req: CreateConceptRequest): Promise<CreateConceptResponse> {
    return this.request<CreateConceptResponse>('/teacher/concepts', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  }

  async getPendingTags(runId: string): Promise<PendingTagsResponse> {
    return this.request<PendingTagsResponse>(`/teacher/concepts/${runId}`);
  }

  async confirmTags(runId: string, req: ConfirmTagsRequest): Promise<ConfirmTagsResponse> {
    return this.request<ConfirmTagsResponse>(`/teacher/concepts/${runId}/confirm`, {
      method: 'POST',
      body: JSON.stringify(req),
    });
  }

  async getTeacherAnalytics(conceptId: string): Promise<TeacherAnalyticsResponse> {
    return this.request<TeacherAnalyticsResponse>(`/teacher/analytics/${conceptId}`);
  }

  async getTeacherTrends(conceptId: string): Promise<TeacherTrendsResponse> {
    return this.request<TeacherTrendsResponse>(`/teacher/trends/${conceptId}`);
  }

  async submitAttempt(req: SubmitAttemptRequest): Promise<SubmitAttemptResponse> {
    return this.request<SubmitAttemptResponse>('/student/attempts', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  }

  async getStudentNotes(conceptId: string): Promise<StudentNotesResponse> {
    return this.request<StudentNotesResponse>(`/student/notes/${conceptId}`);
  }

  async getStudentGraph(): Promise<StudentGraphResponse> {
    return this.request<StudentGraphResponse>('/student/graph');
  }

  async getRunStatus(runId: string): Promise<RunStatusResponse> {
    return this.request<RunStatusResponse>(`/runs/${runId}/status`);
  }
}

export const api = new ApiClient();

