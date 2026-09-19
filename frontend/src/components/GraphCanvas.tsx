import React from "react";
import { ConceptNode, GraphEdge } from "../types/synapse";

export interface GraphCanvasProps {
  nodes: ConceptNode[];
  edges: GraphEdge[];
  onSelectNode?: (node: ConceptNode) => void;
  selectedNodeId?: string;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  nodes,
  edges,
  onSelectNode,
  selectedNodeId,
}) => {
  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center p-12 bg-slate-900 border border-slate-800 rounded-xl text-slate-500 text-sm">
        No concept graph nodes available. Complete an assessment to generate your learning graph.
      </div>
    );
  }

  // Calculate layout coordinates for nodes
  const width = 800;
  const height = 400;
  const radius = 28;

  // Simple layered layout based on prerequisite depth
  const inDegree: Record<string, number> = {};
  nodes.forEach((n) => (inDegree[n.id] = 0));
  edges.forEach((e) => {
    if (e.relationship === "prerequisite" && inDegree[e.to_concept] !== undefined) {
      inDegree[e.to_concept] += 1;
    }
  });

  const layers: Record<number, ConceptNode[]> = {};
  nodes.forEach((n) => {
    const deg = inDegree[n.id] || 0;
    if (!layers[deg]) layers[deg] = [];
    layers[deg].push(n);
  });

  const layerKeys = Object.keys(layers).map(Number).sort((a, b) => a - b);
  const nodePositions: Record<string, { x: number; y: number }> = {};

  layerKeys.forEach((layerIdx, lIndex) => {
    const layerNodes = layers[layerIdx];
    const x = ((lIndex + 1) / (layerKeys.length + 1)) * width;
    layerNodes.forEach((node, nIndex) => {
      const y = ((nIndex + 1) / (layerNodes.length + 1)) * height;
      nodePositions[node.id] = { x, y };
    });
  });

  return (
    <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 overflow-x-auto shadow-inner">
      <svg width={width} height={height} className="w-full h-auto min-w-[600px]">
        <defs>
          <marker
            id="arrowhead"
            markerWidth="8"
            markerHeight="6"
            refX="7"
            refY="3"
            orient="auto"
          >
            <polygon points="0 0, 8 3, 0 6" fill="#64748b" />
          </marker>
        </defs>

        {/* Directed Edges */}
        {edges.map((edge, idx) => {
          const from = nodePositions[edge.from_concept];
          const to = nodePositions[edge.to_concept];
          if (!from || !to) return null;

          // Compute line vector slightly offset for node radius
          const dx = to.x - from.x;
          const dy = to.y - from.y;
          const angle = Math.atan2(dy, dx);
          const startX = from.x + Math.cos(angle) * radius;
          const startY = from.y + Math.sin(angle) * radius;
          const endX = to.x - Math.cos(angle) * (radius + 4);
          const endY = to.y - Math.sin(angle) * (radius + 4);

          return (
            <g key={idx}>
              <line
                x1={startX}
                y1={startY}
                x2={endX}
                y2={endY}
                stroke="#475569"
                strokeWidth="2"
                markerEnd="url(#arrowhead)"
              />
            </g>
          );
        })}

        {/* Concept Nodes */}
        {nodes.map((node) => {
          const pos = nodePositions[node.id];
          if (!pos) return null;
          const isSelected = selectedNodeId === node.id;

          return (
            <g
              key={node.id}
              onClick={() => onSelectNode?.(node)}
              className="cursor-pointer group"
            >
              <circle
                cx={pos.x}
                cy={pos.y}
                r={radius}
                className={`transition-all ${
                  isSelected
                    ? "fill-purple-600 stroke-purple-300 stroke-2"
                    : "fill-slate-800 stroke-slate-600 hover:stroke-sky-400 stroke-1 group-hover:fill-slate-700"
                }`}
              />
              <text
                x={pos.x}
                y={pos.y + 4}
                textAnchor="middle"
                className="fill-slate-100 text-[11px] font-medium pointer-events-none select-none"
              >
                {node.name.slice(0, 8)}
              </text>
              <title>{`${node.name}\n${node.summary}`}</title>
            </g>
          );
        })}
      </svg>
    </div>
  );
};
