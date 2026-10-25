import { create } from "zustand";
import type { AnalysisPayload } from "@/lib/types";

type WorkspaceState = {
  analysis: AnalysisPayload | null;
  imageUrl: string | null;
  selectedClaimId: string | null;
  activeCandidate: number;
  setAnalysis: (analysis: AnalysisPayload, imageUrl: string) => void;
  selectClaim: (id: string | null) => void;
  setCandidate: (index: number) => void;
  clear: () => void;
};

export const useWorkspace = create<WorkspaceState>((set, get) => ({
  analysis: null, imageUrl: null, selectedClaimId: null, activeCandidate: 0,
  setAnalysis: (analysis, imageUrl) => {
    const previous = get().imageUrl;
    if (previous) URL.revokeObjectURL(previous);
    set({ analysis, imageUrl, selectedClaimId: null, activeCandidate: 0 });
  },
  selectClaim: (selectedClaimId) => set({ selectedClaimId }),
  setCandidate: (activeCandidate) => set({ activeCandidate }),
  clear: () => { const previous = get().imageUrl; if (previous) URL.revokeObjectURL(previous); set({ analysis: null, imageUrl: null, selectedClaimId: null, activeCandidate: 0 }); },
}));
