import React from "react";
import { TagConfirmationForm } from "../../components/TagConfirmationForm";
import { Card, Loading } from "../../components/UI";
import { useTagConfirmation } from "../../hooks";
import { ConceptNode } from "../../types/synapse";

export interface TagsPageProps {
  runId: string;
  onConfirmed?: () => void;
}

export const TagsPage: React.FC<TagsPageProps> = ({ runId, onConfirmed }) => {
  const { pending, loading, submitting, error, confirmTags } = useTagConfirmation(runId);

  if (loading) return <Loading message="Loading pending concept tags..." />;

  if (!pending) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <Card>
          <div className="text-center py-8 text-slate-400 text-sm">
            {error || "No pending tags awaiting confirmation for this run."}
          </div>
        </Card>
      </div>
    );
  }

  const handleConfirm = async (editedConcepts: ConceptNode[]) => {
    await confirmTags(editedConcepts);
    if (onConfirmed) {
      onConfirmed();
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Confirm Curriculum Tags</h1>
        <p className="text-sm text-slate-400 mt-1">
          Review extracted concepts and refine tag taxonomy before test generation.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-rose-300 text-sm">
          {error}
        </div>
      )}

      <TagConfirmationForm
        runId={runId}
        conceptName={pending.concept_id}
        initialConcepts={pending.concepts}
        onConfirm={handleConfirm}
        loading={submitting}
      />
    </div>
  );
};
