import React, { useState } from "react";
import { GraphCanvas } from "../../components/GraphCanvas";
import { Card, Loading } from "../../components/UI";
import { useGraph } from "../../hooks";
import { ConceptNode } from "../../types/synapse";

export const GraphPage: React.FC = () => {
  const { nodes, edges, loading, error } = useGraph();
  const [selectedNode, setSelectedNode] = useState<ConceptNode | null>(null);

  if (loading) return <Loading message="Loading curriculum knowledge graph..." />;

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Learning Path & Concept Graph</h1>
        <p className="text-sm text-slate-400 mt-1">
          Explore prerequisite relationships and master concepts step-by-step.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-950/40 border border-rose-800 rounded-xl text-rose-300 text-sm">
          {error}
        </div>
      )}

      <GraphCanvas
        nodes={nodes}
        edges={edges}
        selectedNodeId={selectedNode?.id}
        onSelectNode={(node) => setSelectedNode(node)}
      />

      {selectedNode && (
        <Card title={`Concept: ${selectedNode.name}`}>
          <div className="space-y-3">
            <p className="text-sm text-slate-300 leading-relaxed">{selectedNode.summary}</p>
            {selectedNode.prerequisites.length > 0 ? (
              <div className="pt-2">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  Required Prerequisites
                </span>
                <div className="flex flex-wrap gap-2">
                  {selectedNode.prerequisites.map((pid) => (
                    <span key={pid} className="px-2.5 py-1 bg-slate-800 text-slate-300 rounded text-xs">
                      {pid}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-xs text-emerald-400">Fundamental concept &bull; No prior prerequisites required.</div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
};
