import React, { useState } from "react";
import { QuestionCard } from "../../components/QuestionCard";
import { NoteViewer } from "../../components/NoteViewer";
import { Button, Card, Loading } from "../../components/UI";
import { useAttempt } from "../../hooks";
import { Test } from "../../types/synapse";

export interface AttemptPageProps {
  test: Test;
}

export const AttemptPage: React.FC<AttemptPageProps> = ({ test }) => {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const { submitAnswers, submitting, result, error } = useAttempt(test.id);

  const handleSelectOption = (qid: string, opt: string) => {
    setAnswers((prev) => ({ ...prev, [qid]: opt }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await submitAnswers(answers);
  };

  if (result) {
    return (
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        <Card>
          <div className="flex justify-between items-center mb-4 border-b border-slate-800 pb-3">
            <h1 className="text-2xl font-bold text-slate-100">Assessment Diagnostic Results</h1>
            <span className="text-sm font-semibold bg-purple-950 text-purple-300 border border-purple-800 px-3 py-1 rounded-full">
              Score: {result.attempt.score} / {result.attempt.total}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
              <span className="text-xs text-slate-400 block mb-1">Mastery Estimate</span>
              <span className="text-2xl font-bold text-sky-400">
                {Math.round(result.diagnosis.mastery_estimate * 100)}%
              </span>
            </div>
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
              <span className="text-xs text-slate-400 block mb-1">Current Trend</span>
              <span className="text-2xl font-bold text-purple-400 capitalize">
                {result.diagnosis.trend.replace("_", " ")}
              </span>
            </div>
          </div>
        </Card>

        {/* Private Tailored Study Note */}
        <NoteViewer note={result.note} />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-100">Diagnostic Assessment: {test.concept_name}</h1>
        <p className="text-sm text-slate-400 mt-1">
          Complete the questions to generate a tailored note addressing your focus areas.
        </p>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-rose-300 text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {test.questions.map((q, idx) => (
          <QuestionCard
            key={q.id}
            question={q}
            index={idx}
            selectedOption={answers[q.id]}
            onSelectOption={handleSelectOption}
          />
        ))}

        <div className="pt-4 flex justify-end">
          <Button type="submit" disabled={submitting || Object.keys(answers).length === 0}>
            {submitting ? "Analyzing Answers..." : "Submit Diagnostic Assessment"}
          </Button>
        </div>
      </form>
    </div>
  );
};
