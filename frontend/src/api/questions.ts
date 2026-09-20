import { apiFetch } from './client';
import { Question } from '../shared/types';

export async function getRunQuestions(runId: string): Promise<Question[]> {
  return apiFetch<Question[]>(`/runs/${runId}/questions`);
}

export async function getQuestion(questionId: string): Promise<Question> {
  return apiFetch<Question>(`/questions/${questionId}`);
}

export async function answerQuestion(
  questionId: string,
  answer: string,
  who = 'expert'
): Promise<Question> {
  return apiFetch<Question>(`/questions/${questionId}/answer`, {
    method: 'POST',
    body: JSON.stringify({ answer, who }),
  });
}
