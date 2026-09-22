// frontend/src/student/GraphCanvas.tsx
import React, { useState, useRef } from 'react';
import type { ConceptNode, GraphEdge } from '../types/synapse';
import type { BrainNode } from '../shared/brainData';
import {
  Brain,
  Search,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  FileText,
  Layers,
  Activity,
} from 'lucide-react';

interface GraphCanvasProps {
  nodes: (ConceptNode | BrainNode)[];
  edges: GraphEdge[];
  onSelectNode?: (node: ConceptNode) => void;
  onTakeTest?: (node: ConceptNode) => void;
  onViewNotes?: (node: ConceptNode) => void;
  hasNotesForNode?: (nodeId: string) => boolean;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  nodes,
  edges,
  onSelectNode,
  onTakeTest,
  onViewNotes,
  hasNotesForNode,
}) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(nodes[0]?.id || null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });

  const width = 1000;
  const height = 580;

  // Build coordinate map from BrainNode coordinates or compute organic layout
  const nodeMap = new Map<string, { x: number; y: number; category?: string; node: ConceptNode | BrainNode }>();
  nodes.forEach((n, idx) => {
    const bn = n as BrainNode;
    if (typeof bn.x === 'number' && typeof bn.y === 'number') {
      nodeMap.set(n.id, { x: bn.x, y: bn.y, category: bn.category, node: n });
    } else {
      // Automatic fallback circle layout
      const angle = (idx / nodes.length) * 2 * Math.PI - Math.PI / 2;
      nodeMap.set(n.id, {
        x: width / 2 + 280 * Math.cos(angle),
        y: height / 2 + 180 * Math.sin(angle),
        node: n,
      });
    }
  });

  const selectedEntry = selectedNodeId ? nodeMap.get(selectedNodeId) : null;
  const selectedNode = selectedEntry?.node || null;

  // Compute prerequisites and dependents for highlighting
  const prereqSet = new Set(
    edges.filter((e) => e.to_concept === selectedNodeId).map((e) => e.from_concept)
  );
  const dependentSet = new Set(
    edges.filter((e) => e.from_concept === selectedNodeId).map((e) => e.to_concept)
  );

  const getCategoryColor = (cat?: string) => {
    switch (cat) {
      case 'foundations':
        return '#38bdf8'; // Cyan
      case 'algorithms':
        return '#818cf8'; // Indigo
      case 'deep_learning':
        return '#10b981'; // Emerald
      case 'cognitive_agents':
        return '#c084fc'; // Purple
      default:
        return '#38bdf8';
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).tagName === 'circle' || (e.target as HTMLElement).tagName === 'text') return;
    setIsDragging(true);
    dragStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y,
    });
  };

  const handleMouseUp = () => setIsDragging(false);

  const filteredNodes = nodes.filter((n) => {
    const matchesSearch = n.name.toLowerCase().includes(searchQuery.toLowerCase());
    const bn = n as BrainNode;
    const matchesCat = selectedCategory === 'all' || bn.category === selectedCategory;
    return matchesSearch && matchesCat;
  });

  return (
    <div className="glass-card" style={{ padding: '1.25rem', position: 'relative' }}>
      {/* Top Header Controls */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem',
        marginBottom: '1rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div style={{
            background: 'rgba(168, 85, 247, 0.2)',
            color: '#c084fc',
            padding: '0.45rem',
            borderRadius: 'var(--radius-sm)',
            display: 'flex',
          }}>
            <Brain size={20} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
              Neural Knowledge Lobe &bull; Dynamic Cognitive Graph
            </h3>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              {nodes.length} Interconnected Concepts &bull; {edges.length} Synaptic Pathways
            </span>
          </div>
        </div>

        {/* Search Bar & Category Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', minWidth: '220px' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              className="input-text"
              placeholder="Search brain concepts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ paddingLeft: '2rem', height: '34px', fontSize: '0.8rem' }}
            />
          </div>

          <div style={{ display: 'flex', gap: '0.3rem', background: 'rgba(15, 23, 42, 0.8)', padding: '0.2rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            {['all', 'foundations', 'algorithms', 'deep_learning', 'cognitive_agents'].map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                style={{
                  border: 'none',
                  background: selectedCategory === cat ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
                  color: selectedCategory === cat ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  padding: '0.25rem 0.6rem',
                  borderRadius: '4px',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  textTransform: 'capitalize',
                }}
              >
                {cat.replace('_', ' ')}
              </button>
            ))}
          </div>

          {/* Zoom Controls */}
          <div style={{ display: 'flex', gap: '0.2rem' }}>
            <button
              className="btn btn-secondary"
              style={{ padding: '0.3rem 0.55rem' }}
              onClick={() => setZoom((z) => Math.min(z + 0.15, 2))}
              title="Zoom In"
            >
              <ZoomIn size={14} />
            </button>
            <button
              className="btn btn-secondary"
              style={{ padding: '0.3rem 0.55rem' }}
              onClick={() => setZoom((z) => Math.max(z - 0.15, 0.6))}
              title="Zoom Out"
            >
              <ZoomOut size={14} />
            </button>
            <button
              className="btn btn-secondary"
              style={{ padding: '0.3rem 0.55rem' }}
              onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
              title="Reset View"
            >
              <Maximize2 size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Canvas & Inspector Layout */}
      <div className="graph-layout-grid">
        {/* SVG Brain Canvas */}
        <div
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          style={{
            background: 'radial-gradient(ellipse at 50% 50%, #0d1527 0%, #060911 100%)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid rgba(56, 189, 248, 0.2)',
            overflow: 'hidden',
            cursor: isDragging ? 'grabbing' : 'grab',
            position: 'relative',
            height: '560px',
            boxShadow: 'inset 0 0 50px rgba(0, 0, 0, 0.8)',
          }}
        >
          {/* Subtle Hemisphere Background Overlay */}
          <div style={{
            position: 'absolute',
            inset: 0,
            backgroundImage: `
              radial-gradient(circle at 30% 50%, rgba(56, 189, 248, 0.04) 0%, transparent 60%),
              radial-gradient(circle at 70% 50%, rgba(192, 132, 252, 0.04) 0%, transparent 60%)
            `,
            pointerEvents: 'none',
          }} />

          <svg
            viewBox={`0 0 ${width} ${height}`}
            style={{ width: '100%', height: '100%' }}
          >
            <defs>
              <marker
                id="synapse-arrow"
                viewBox="0 0 10 10"
                refX="24"
                refY="5"
                markerWidth="5"
                markerHeight="5"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(56, 189, 248, 0.7)" />
              </marker>

              <marker
                id="synapse-arrow-highlight"
                viewBox="0 0 10 10"
                refX="24"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8" />
              </marker>

              {/* Glowing Filters */}
              <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
            </defs>

            <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`} style={{ transformOrigin: 'center center' }}>
              {/* Left & Right Hemisphere Labels */}
              <text x="250" y="50" fill="rgba(255,255,255,0.15)" fontSize="14" fontWeight="800" letterSpacing="0.2em">
                LEFT LOBE: LOGIC & ALGORITHMS
              </text>
              <text x="630" y="50" fill="rgba(255,255,255,0.15)" fontSize="14" fontWeight="800" letterSpacing="0.2em">
                RIGHT LOBE: NEURAL & AGENTS
              </text>

              {/* Render Synaptic Connections / Edges */}
              {edges.map((edge, idx) => {
                const from = nodeMap.get(edge.from_concept);
                const to = nodeMap.get(edge.to_concept);
                if (!from || !to) return null;

                const isConnected =
                  edge.from_concept === selectedNodeId || edge.to_concept === selectedNodeId;

                // Bezier curve control points for organic neural appearance
                const dx = to.x - from.x;
                const dy = to.y - from.y;
                const cx = (from.x + to.x) / 2 - dy * 0.15;
                const cy = (from.y + to.y) / 2 + dx * 0.15;

                return (
                  <path
                    key={`edge-${idx}`}
                    d={`M ${from.x} ${from.y} Q ${cx} ${cy} ${to.x} ${to.y}`}
                    fill="none"
                    stroke={
                      isConnected
                        ? edge.from_concept === selectedNodeId
                          ? '#c084fc'
                          : '#38bdf8'
                        : 'rgba(255, 255, 255, 0.12)'
                    }
                    strokeWidth={isConnected ? 2.5 : 1.2}
                    strokeDasharray={edge.relationship === 'related' ? '4,4' : undefined}
                    markerEnd={isConnected ? 'url(#synapse-arrow-highlight)' : 'url(#synapse-arrow)'}
                    style={{ transition: 'stroke 0.2s ease, stroke-width 0.2s ease' }}
                  />
                );
              })}

              {/* Render Brain Concept Nodes */}
              {filteredNodes.map((node) => {
                const entry = nodeMap.get(node.id);
                if (!entry) return null;
                const { x, y, category } = entry;

                const isSelected = node.id === selectedNodeId;
                const isPrereq = prereqSet.has(node.id);
                const isDependent = dependentSet.has(node.id);
                const catColor = getCategoryColor(category);

                return (
                  <g
                    key={node.id}
                    transform={`translate(${x}, ${y})`}
                    style={{ cursor: 'pointer' }}
                    onClick={() => {
                      setSelectedNodeId(node.id);
                      onSelectNode?.(node);
                    }}
                  >
                    {/* Outer Synaptic Halo / Glow */}
                    <circle
                      r={isSelected ? 32 : isPrereq || isDependent ? 25 : 18}
                      fill={
                        isSelected
                          ? 'rgba(56, 189, 248, 0.2)'
                          : isPrereq
                          ? 'rgba(16, 185, 129, 0.15)'
                          : isDependent
                          ? 'rgba(192, 132, 252, 0.15)'
                          : 'rgba(15, 23, 42, 0.8)'
                      }
                      stroke={
                        isSelected
                          ? '#38bdf8'
                          : isPrereq
                          ? '#34d399'
                          : isDependent
                          ? '#c084fc'
                          : catColor
                      }
                      strokeWidth={isSelected ? 3 : 1.5}
                      filter={isSelected ? 'url(#glow)' : undefined}
                      style={{ transition: 'all 0.2s ease' }}
                    />

                    {/* Central Nucleus */}
                    <circle
                      r={isSelected ? 14 : 9}
                      fill={isSelected ? '#38bdf8' : catColor}
                      opacity={isSelected ? 1 : 0.8}
                    />

                    {/* Node Text Label */}
                    <text
                      textAnchor="middle"
                      dy={isSelected ? 42 : 30}
                      fill={isSelected ? '#fff' : '#cbd5e1'}
                      fontSize={isSelected ? '12' : '10'}
                      fontWeight={isSelected ? '800' : '600'}
                      fontFamily="var(--font-main)"
                      style={{
                        paintOrder: 'stroke',
                        stroke: 'rgba(9, 13, 22, 0.95)',
                        strokeWidth: 3,
                        strokeLinecap: 'round',
                        strokeLinejoin: 'round',
                      }}
                    >
                      {node.name}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>

        {/* Selected Concept Deep Inspector */}
        <div style={{
          background: 'rgba(13, 21, 39, 0.85)',
          padding: '1.5rem',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}>
          {selectedNode ? (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.8rem' }}>
                <span className="badge" style={{
                  background: `${getCategoryColor((selectedNode as BrainNode).category)}20`,
                  color: getCategoryColor((selectedNode as BrainNode).category),
                  border: `1px solid ${getCategoryColor((selectedNode as BrainNode).category)}40`,
                  textTransform: 'capitalize',
                  fontSize: '0.72rem',
                }}>
                  {(selectedNode as BrainNode).category?.replace('_', ' ') || 'Concept Node'}
                </span>
                {hasNotesForNode?.(selectedNode.id) && (
                  <span className="badge badge-improving" style={{ fontSize: '0.7rem' }}>
                    <ShieldCheck size={12} /> Notes Ready
                  </span>
                )}
              </div>

              <h4 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', marginBottom: '0.5rem', lineHeight: 1.3 }}>
                {selectedNode.name}
              </h4>

              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '1.25rem' }}>
                {selectedNode.summary || 'Essential building block in the neural cognitive curriculum.'}
              </p>

              {/* Prerequisites Breakdown */}
              <div style={{ marginBottom: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '0.4rem' }}>
                  <Layers size={12} /> Prerequisites ({prereqSet.size})
                </div>
                {prereqSet.size > 0 ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                    {Array.from(prereqSet).map((pId) => {
                      const pNode = nodeMap.get(pId)?.node;
                      return (
                        <span key={pId} className="badge badge-stable" style={{ fontSize: '0.7rem' }}>
                          {pNode?.name || pId}
                        </span>
                      );
                    })}
                  </div>
                ) : (
                  <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Root Foundation Node (No prerequisites)</span>
                )}
              </div>

              {/* Downstream Unlocks */}
              <div style={{ marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '0.4rem' }}>
                  <Activity size={12} /> Unlocks Next ({dependentSet.size})
                </div>
                {dependentSet.size > 0 ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                    {Array.from(dependentSet).map((dId) => {
                      const dNode = nodeMap.get(dId)?.node;
                      return (
                        <span key={dId} className="badge badge-declining" style={{ fontSize: '0.7rem' }}>
                          {dNode?.name || dId}
                        </span>
                      );
                    })}
                  </div>
                ) : (
                  <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Advanced Apex Node</span>
                )}
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              Click any neuron in the brain to inspect synaptic prerequisites and conduct diagnostic testing.
            </div>
          )}

          {/* Interactive Actions for Selected Node */}
          {selectedNode && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '1rem' }}>
              <button
                className="btn btn-primary"
                onClick={() => onTakeTest?.(selectedNode)}
                style={{ width: '100%', fontSize: '0.85rem' }}
              >
                Take Diagnostic Test <ArrowRight size={14} />
              </button>

              {hasNotesForNode?.(selectedNode.id) && (
                <button
                  className="btn btn-secondary"
                  onClick={() => onViewNotes?.(selectedNode)}
                  style={{ width: '100%', fontSize: '0.85rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem' }}
                >
                  <FileText size={14} /> Read Private Notes
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
