import React from "react";
import { NoteVersion } from "../types/synapse";

export interface NoteViewerProps {
  note: NoteVersion;
}

export const NoteViewer: React.FC<NoteViewerProps> = ({ note }) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Personalized Study Guide</h2>
          <span className="text-xs text-slate-400">
            Concept: {note.concept_id} &bull; Revision v{note.version}
          </span>
        </div>
        <span className="bg-emerald-950 text-emerald-400 border border-emerald-800 text-xs px-2.5 py-1 rounded-full font-medium">
          Verified Private Note
        </span>
      </div>

      <div className="prose prose-invert max-w-none text-slate-300 leading-relaxed whitespace-pre-wrap font-sans text-sm">
        {note.markdown}
      </div>
    </div>
  );
};
