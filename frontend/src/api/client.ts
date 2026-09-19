/**
 * Typed API client for Synapse backend endpoints.
 * Authoritative contract: Contracts.md Sections C.4, C.6, D.9.
 * Uses GENERATED types from frontend/src/types/synapse.ts.
 */
import {
  ConceptNode,
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
  Test,
} from "../types/synapse";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: any
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ClientConfig {
  baseUrl?: string;
  getToken?: () => string | null;
}

export class SynapseApiClient {
  private baseUrl: string;
  private getToken?: () => string | null;

  constructor(config: ClientConfig = {}) {
    this.baseUrl = config.baseUrl || "http://localhost:8000";
    this.getToken = config.getToken;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string> || {}),
    };

    if (this.getToken) {
      const token = this.getToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorDetail = response.statusText;
      try {
        const errJson = await response.json();
        errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
      } catch {
        // use statusText
      }
      throw new ApiError(response.status, errorDetail);
    }

    return response.json() as Promise<T>;
  }

  // ── Teacher Endpoints ──

  async createConcept(data: CreateConceptRequest): Promise<CreateConceptResponse> {
    return this.request<CreateConceptResponse>("/teacher/concepts", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getPendingTags(runId: string): Promise<PendingTagsResponse> {
    return this.request<PendingTagsResponse>(`/teacher/concepts/${runId}`);
  }

  async confirmTags(runId: string, data: ConfirmTagsRequest): Promise<ConfirmTagsResponse> {
    if (runId !== data.run_id) {
      throw new ApiError(422, "Path run_id does not match request body run_id");
    }
    return this.request<ConfirmTagsResponse>(`/teacher/concepts/${runId}/confirm`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getTeacherTest(runId: string): Promise<Test> {
    return this.request<Test>(`/teacher/tests/${runId}`);
  }

  async getTeacherAnalytics(conceptId: string): Promise<TeacherAnalyticsResponse> {
    return this.request<TeacherAnalyticsResponse>(`/teacher/analytics/${conceptId}`);
  }

  async getTeacherTrends(conceptId: string): Promise<TeacherTrendsResponse> {
    return this.request<TeacherTrendsResponse>(`/teacher/trends/${conceptId}`);
  }

  // ── Student Endpoints ──

  async submitAttempt(data: SubmitAttemptRequest): Promise<SubmitAttemptResponse> {
    return this.request<SubmitAttemptResponse>("/student/attempts", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async getStudentNotes(conceptId: string): Promise<StudentNotesResponse> {
    return this.request<StudentNotesResponse>(`/student/notes/${conceptId}`);
  }

  async getStudentGraph(): Promise<StudentGraphResponse> {
    return this.request<StudentGraphResponse>("/student/graph");
  }

  // ── Runtime Endpoints ──

  async getRunStatus(runId: string): Promise<RunStatusResponse> {
    return this.request<RunStatusResponse>(`/runs/${runId}/status`);
  }
}

export const apiClient = new SynapseApiClient();
