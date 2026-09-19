import React, { useState } from "react";
import { ConceptNode } from "../types/synapse";
import { Button } from "./UI";

export interface TagConfirmationFormProps {
  runId: string;
  conceptName: string;
  initialConcepts: ConceptNode[];
  onConfirm: (editedConcepts: ConceptNode[]) => Promise<void>;
  loading?: boolean;
}

export const TagConfirmationForm: React.FC<TagConfirmationFormProps> = ({
  runId,
  conceptName,
  initialConcepts,
  onConfirm,
  loading = false,
}) => {
  const [concepts, setConcepts] = useState<ConceptNode[]>(initialConcepts);

  const handleUpdate = (index: number, field: "name" | "summary", val: string) => {
    const next = [...concepts];
    next[index] = { ...next[index], [field]: val };
    setConcepts(next);
  };

  const handleAdd = () => {
    setConcepts([
      ...concepts,
      {
        id: `c_custom_${Date.now()}`,
        name: "New Subconcept",
        summary: "Description of fundamental mechanisms.",
        prerequisites: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);
  };

  const handleRemove = (index: number) => {
    setConcepts(concepts.filter((_, i) => i !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConfirm(concepts);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="bg-sky-950/40 border border-sky-800/80 rounded-xl p-4 text-sky-200 text-sm">
        Review curriculum concepts extracted for <strong>{conceptName}</strong> (Run: {runId}).
        Confirm or modify tags to tailor the diagnostic test.
      </div>

      <div className="space-y-4">
        {concepts.map((concept, index) => (
          <div key={concept.id || index} className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-xs font-semibold text-slate-400">Concept #{index + 1}</span>
              <button
                type="button"
                onClick={() => handleRemove(index)}
                className="text-xs text-rose-400 hover:text-rose-300"
              >
                Remove
              </button>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">Concept Name</label>
              <input
                type="text"
                value={concept.name}
                onChange={(e) => handleUpdate(index, "name", e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 text-sm focus:border-sky-500 focus:outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">Summary / Definition</label>
              <textarea
                value={concept.summary}
                onChange={(e) => handleUpdate(index, "summary", e.target.value)}
                rows={2}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 text-sm focus:border-sky-500 focus:outline-none"
                required
              />
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between pt-4 border-t border-slate-800">
        <Button type="button" variant="secondary" size="sm" onClick={handleAdd}>
          + Add Concept Tag
        </Button>
        <Button type="submit" variant="primary" disabled={loading}>
          {loading ? "Confirming..." : "Confirm Concepts & Generate Test"}
        </Button>
      </div>
    </form>
  );
};
