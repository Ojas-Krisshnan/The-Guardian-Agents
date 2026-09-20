import React from "react";
import { TestQuestion } from "../types/synapse";

export interface QuestionCardProps {
  question: TestQuestion;
  index: number;
  selectedOption?: string;
  onSelectOption: (questionId: string, option: string) => void;
}

export const QuestionCard: React.FC<QuestionCardProps> = ({
  question,
  index,
  selectedOption,
  onSelectOption,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-4 shadow-sm">
      <div className="text-slate-200 font-medium mb-3">
        <span className="text-purple-400 font-bold mr-2">Q{index + 1}.</span>
        {question.text}
      </div>
      <div className="space-y-2">
        {question.options.map((opt, i) => {
          const isSelected = selectedOption === opt;
          return (
            <label
              key={i}
              className={`flex items-center p-3 rounded-lg border transition cursor-pointer ${
                isSelected
                  ? "bg-purple-950/40 border-purple-500 text-purple-200"
                  : "bg-slate-800/60 border-slate-700 hover:border-slate-600 text-slate-300"
              }`}
            >
              <input
                type="radio"
                name={`q_${question.id}`}
                value={opt}
                checked={isSelected}
                onChange={() => onSelectOption(question.id, opt)}
                className="w-4 h-4 text-purple-600 bg-slate-900 border-slate-700 focus:ring-purple-500"
              />
              <span className="ml-3 text-sm">{opt}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
};
