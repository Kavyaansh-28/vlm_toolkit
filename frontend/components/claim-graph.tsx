"use client";

import dynamic from "next/dynamic";
import { useWorkspace } from "@/lib/store";
import type { Candidate, ClaimGraph as GraphData } from "@/lib/types";

const GraphCanvas = dynamic(() => import("@/components/claim-graph-canvas"), {
  ssr: false,
  loading: () => <div className="grid h-[330px] place-items-center text-[10px] text-zinc-600">Loading graph canvas…</div>,
});

export function ClaimGraph({ graph, selectedCandidate }: { graph?: GraphData; selectedCandidate?: Candidate }) {
  const selected = useWorkspace((state) => state.selectedClaimId);
  const choose = useWorkspace((state) => state.selectClaim);
  if (!graph?.nodes?.length) return <div className="grid h-64 place-items-center rounded-xl border border-dashed border-white/[.08] text-xs text-zinc-600">No claim graph data was returned for this response.</div>;
  return <GraphCanvas graph={graph} selectedClaimId={selected} onSelectClaim={choose} candidate={selectedCandidate}/>;
}
