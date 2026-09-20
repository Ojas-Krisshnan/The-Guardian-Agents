import { getRuns, createRun, getRun, advanceRun, getReplay } from '../api/runs';
import { getRunQuestions, getQuestion, answerQuestion } from '../api/questions';
import { Run, Question, Version } from '../shared/types';

export const teacherApi = {
  getRuns: (): Promise<Run[]> => getRuns(),
  createRun: (domain = 'demo', meta: Record<string, any> = {}): Promise<Run> => createRun(domain, meta),
  getRun: (runId: string): Promise<Run> => getRun(runId),
  advanceRun: (runId: string): Promise<Run> => advanceRun(runId),
  getRunQuestions: (runId: string): Promise<Question[]> => getRunQuestions(runId),
  getQuestion: (questionId: string): Promise<Question> => getQuestion(questionId),
  answerQuestion: (questionId: string, answer: string, who = 'teacher'): Promise<Question> =>
    answerQuestion(questionId, answer, who),
  getReplay: (runId: string): Promise<Version[]> => getReplay(runId),
};
