import { getRuns, getRun, advanceRun, getReplay } from '../api/runs';
import { getRunQuestions } from '../api/questions';
import { Run, Question, Version } from '../shared/types';

export const studentApi = {
  getRuns: (): Promise<Run[]> => getRuns(),
  getRun: (runId: string): Promise<Run> => getRun(runId),
  advanceRun: (runId: string): Promise<Run> => advanceRun(runId),
  getRunQuestions: (runId: string): Promise<Question[]> => getRunQuestions(runId),
  getReplay: (runId: string): Promise<Version[]> => getReplay(runId),
};
