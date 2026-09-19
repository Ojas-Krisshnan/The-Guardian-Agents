import React, { useState } from "react";
import { Button, Card } from "../../components/UI";
import { useConcepts } from "../../hooks";

export interface ConceptsPageProps {
  onRunCreated?: (runId: string) => void;
}

export const ConceptsPage: React.FC<ConceptsPageProps> = ({ onRunCreated }) => {
  const [conceptName, setConceptName] = useState("");
  const [markdown, setMarkdown] = useState("");
  const { createConcept, loading, error } = useConcepts();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!conceptName.trim() || !markdown.trim()) return;
    try {
      const res = await createConcept(markdown, conceptName);
      if (onRunCreated) {
        onRunCreated(res.run_id);
      }
    } catch {
      // Handled by hook error
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Curriculum Concept Extraction</h1>
        <p className="text-sm text-slate-400 mt-1">
          Paste teacher lecture notes to extract structured concepts, wiki-link prerequisites, and prepare diagnostic tests.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-rose-300 text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <Card title="New Curriculum Topic">
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">
                Concept / Topic Name
              </label>
              <input
                type="text"
                value={conceptName}
                onChange={(e) => setConceptName(e.target.value)}
                placeholder="e.g., Photosynthesis & Cellular Respiration"
                className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 text-sm focus:border-sky-500 focus:outline-none"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">
                Teacher Lecture Notes (Markdown)
              </label>
              <textarea
                value={markdown}
                onChange={(e) => setMarkdown(e.target.value)}
                rows={10}
                placeholder="Paste Markdown lecture notes with headings (## Concept) and [[Prerequisite]] references..."
                className="w-full px-4 py-2.5 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 text-sm font-mono focus:border-sky-500 focus:outline-none"
                required
              />
            </div>

            <div className="flex justify-end pt-2">
              <Button type="submit" disabled={loading}>
                {loading ? "Extracting Concepts..." : "Extract Concepts & Begin Tag Confirmation"}
              </Button>
            </div>
          </div>
        </Card>
      </form>
    </div>
  );
};
