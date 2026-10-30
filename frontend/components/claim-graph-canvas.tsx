"use client";

import { useMemo } from "react";
import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from "@xyflow/react";
import type { Candidate, ClaimGraph as GraphData } from "@/lib/types";

export default function ClaimGraphCanvas({ graph, selectedClaimId, onSelectClaim, candidate }: { graph: GraphData; selectedClaimId: string | null; onSelectClaim: (id: string | null) => void; candidate?: Candidate }) {
  const { nodes, edges } = useMemo(() => {
    const rowByKind = new Map<string, number>();
    const xs: Record<string, number> = { object: 30, object_instance: 190, attribute_value: 370, quantity: 370 };
    const nodeClaimIds = new Map<string, string[]>();
    graph.edges.forEach((edge) => { if (!edge.claim_id) return; for (const node of [edge.source, edge.target]) nodeClaimIds.set(node, [...(nodeClaimIds.get(node) ?? []), edge.claim_id]); });
    const nodes: Node[] = graph.nodes.map((node) => {
      const kind = node.kind ?? "object";
      const row = rowByKind.get(kind) ?? 0; rowByKind.set(kind, row + 1);
      const claimIds = nodeClaimIds.get(node.id) ?? [];
      const active = selectedClaimId ? claimIds.includes(selectedClaimId) : false;
      const item = claimIds.map((id) => candidate?.evidence.find((entry) => entry.claim_id === id)).find(Boolean);
      return { id: node.id, position: { x: xs[kind] ?? 30, y: 35 + row * 105 }, data: { label: <div className={`flow-node ${active ? "selected" : ""}`}><div className="text-[9px] text-violet-200/65">{kind.replaceAll("_", " ").toUpperCase()}</div><div className="mt-1 text-[11px]">{node.label}</div>{item && <div className={`mt-1 text-[9px] ${item.status === "SUPPORTED" ? "text-emerald-200" : item.status === "AMBIGUOUS" ? "text-amber-100" : "text-rose-200"}`}>{item.status}</div>}</div> }, style: { background: "transparent", border: "none", width: 140 } };
    });
    const edges: Edge[] = graph.edges.filter((edge) => graph.nodes.some((node) => node.id === edge.source) && graph.nodes.some((node) => node.id === edge.target)).map((edge, index) => ({
      id: `${edge.source}-${edge.target}-${index}`, source: edge.source, target: edge.target, label: edge.label,
      type: "smoothstep", animated: Boolean(edge.claim_id && edge.claim_id === selectedClaimId),
      style: { stroke: edge.claim_id === selectedClaimId ? "#b7a1ff" : "#575968", strokeWidth: edge.claim_id === selectedClaimId ? 2 : 1 },
      labelStyle: { fill: "#a8a8b2", fontSize: 9 }, labelBgStyle: { fill: "#111318" }, labelBgPadding: [4, 3],
      markerEnd: { type: MarkerType.ArrowClosed, color: edge.claim_id === selectedClaimId ? "#b7a1ff" : "#575968", width: 12, height: 12 },
    }));
    return { nodes, edges };
  }, [graph, selectedClaimId, candidate]);

  const onNodeClick = (_event: React.MouseEvent, node: Node) => {
    const claim = graph.edges.find((edge) => edge.claim_id && (edge.source === node.id || edge.target === node.id))?.claim_id;
    onSelectClaim(claim ?? null);
  };
  const onEdgeClick = (_event: React.MouseEvent, edge: Edge) => onSelectClaim(graph.edges.find((item, index) => `${item.source}-${item.target}-${index}` === edge.id)?.claim_id ?? null);

  return <div className="h-[350px] overflow-hidden rounded-xl border border-white/[.055] bg-[#0d0e12]"><ReactFlow nodes={nodes} edges={edges} fitView fitViewOptions={{ padding: .18 }} minZoom={.45} maxZoom={1.7} nodesDraggable={false} nodesConnectable={false} onNodeClick={onNodeClick} onEdgeClick={onEdgeClick}><Background color="#ffffff" gap={24} size={1}/><Controls position="bottom-left" showInteractive={false}/></ReactFlow></div>;
}
