import React from "react";
import { NoteViewer } from "../../components/NoteViewer";
import { Card, Loading } from "../../components/UI";
import { useNotes } from "../../hooks";

export interface NotesPageProps {
  conceptId: string;
}

export const NotesPage: React.FC<NotesPageProps> = ({ conceptId }) => {
  const { notes, loading, error } = useNotes(conceptId);

  if (loading) return <Loading message="Loading your personal study notes..." />;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">My Study Notes</h1>
        <p className="text-sm text-slate-400 mt-1">
          Private, personalized study materials tailored to your diagnosed knowledge gaps.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-rose-300 text-sm">
          {error}
        </div>
      )}

      {notes.length === 0 ? (
        <Card>
          <div className="text-center py-8 text-slate-400 text-sm">
            No notes found for concept <strong>{conceptId}</strong>. Complete an assessment to generate your personalized study guide.
          </div>
        </Card>
      ) : (
        <div className="space-y-6">
          {notes.map((note, idx) => (
            <NoteViewer key={idx} note={note} />
          ))}
        </div>
      )}
    </div>
  );
};
