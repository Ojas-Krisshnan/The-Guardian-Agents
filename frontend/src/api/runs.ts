import { apiFetch } from './client';
import { Run, Version } from '../shared/types';

export async function createRun(
  domain = 'demo',
  meta: Record<string, any> = {}
): Promise<Run> {
  return apiFetch<Run>('/runs', {
    method: 'POST',
    body: JSON.stringify({ domain, meta }),
  });
}

export async function getRuns(limit = 50): Promise<Run[]> {
  return apiFetch<Run[]>(`/runs?limit=${limit}`);
}

export async function getRun(runId: string): Promise<Run> {
  return apiFetch<Run>(`/runs/${runId}`);
}

export async function advanceRun(runId: string): Promise<Run> {
  return apiFetch<Run>(`/runs/${runId}/advance`, {
    method: 'POST',
  });
}

export async function getReplay(runId: string): Promise<Version[]> {
  return apiFetch<Version[]>(`/runs/${runId}/replay`);
}
