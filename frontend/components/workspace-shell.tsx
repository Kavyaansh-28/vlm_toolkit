"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { motion } from "motion/react";
import dynamic from "next/dynamic";
import { Activity, ArrowRight, ChevronDown, CircleHelp, Clock3, Database, Download, FileImage, ImagePlus, Layers3, LoaderCircle, ScanEye, ShieldAlert, ShieldCheck, SlidersHorizontal, Sparkles, X } from "lucide-react";
import { TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";
import { toast } from "sonner";
import { SiteHeader } from "@/components/site-header";
import { Button, EmptyState, Eyebrow, PageHeading, Panel, Pill } from "@/components/ui";
import { analyzeImage, getBenchmarks, getConfig, getHistory, getHistoryItem } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import type { Candidate, Claim, Evidence, HistorySummary } from "@/lib/types";
import { ClaimGraph } from "@/components/claim-graph";

const formSchema = z.object({
  query: z.string().min(1, "Enter a question for the model.").max(2000),
  provider: z.string().min(1, "Select a provider."),
  candidateCount: z.number().int().min(1).max(3),
  manualResponse: z.string().max(12000),
  verificationWeight: z.number().min(0).max(1), agreementWeight: z.number().min(0).max(1),
});
type AnalysisForm = z.infer<typeof formSchema>;
const CandidateChart = dynamic(() => import("@/components/candidate-chart"), { ssr: false, loading: () => <div className="grid h-64 place-items-center text-[10px] text-zinc-600">Loading comparison chart…</div> });

const titles: Record<string, [string, string, string]> = {
  analyze: ["01 / Analyze", "Verify an image, claim by claim.", "Run the existing VLM reliability pipeline and inspect its real output."],
  claims: ["02 / Claims", "A response, decomposed.", "Inspect typed claims and the graph structure extracted by the current backend."],
  evidence: ["03 / Evidence", "Trace the visual support.", "Review Grounding DINO regions, crop-level attribute evidence, contradictions, and uncertainty."],
  candidates: ["04 / Candidates", "Compare what the model said.", "Rank the actual candidates returned by this run; no synthetic comparison scores."],
  evaluation: ["05 / Evaluation", "Benchmarks, as measured.", "POPE and CHAIR results appear only after a benchmark run has been processed."],
  experiments: ["06 / Experiments", "Every run, traceable.", "Browse and reopen records saved by the existing SQLite experiment history."],
};

function actionTone(action?: string): "good" | "warn" | "bad" | "neutral" | "violet" {
  if (action === "ACCEPT") return "good";
  if (action === "CORRECT") return "violet";
  if (action === "ABSTAIN") return "warn";
  return "neutral";
}

function claimLabel(claim: Claim) {
  if (claim.type === "attribute") return `${claim.subject} is ${claim.value}`;
  if (claim.type === "quantity") return `${claim.value} × ${claim.subject}`;
  if (claim.type === "relation") return `${claim.subject} ${String(claim.value ?? "").replace("_", " ")} ${claim.object ?? ""}`;
  return `${claim.subject} exists`;
}

function detailLabel(detail?: string) {
  if (!detail || detail === "flag") return detail === "flag" ? "flagged as uncertain" : "";
  if (detail === "delete") return "delete (no evidence)";
  const [kind, rest] = detail.split(":");
  if (kind === "replace") return `replace ${rest.replace("->", " → ")}`;
  if (kind === "swap") return `swap ${rest.replace("<->", " ↔ ")}`;
  if (kind === "recount") return `recount ${rest.replace("->", " → ")}`;
  return detail;
}

type Segment = { kind: "same" | "del" | "add"; text: string };
function wordDiff(before: string, after: string): Segment[] {
  const a = before.split(/(\s+)/), b = after.split(/(\s+)/);
  const table = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) for (let j = b.length - 1; j >= 0; j--) table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
  const out: Segment[] = [];
  let i = 0, j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) { out.push({ kind: "same", text: a[i] }); i++; j++; }
    else if (j < b.length && (i >= a.length || table[i][j + 1] >= table[i + 1][j])) { out.push({ kind: "add", text: b[j] }); j++; }
    else { out.push({ kind: "del", text: a[i] }); i++; }
  }
  return out;
}

function statusTone(status?: string): "good" | "warn" | "bad" | "neutral" | "violet" {
  if (status === "SUPPORTED" || status === "ACCEPT" || status === "RERANK") return "good";
  if (status === "CORRECT") return "violet";
  if (status === "AMBIGUOUS" || status === "ABSTAIN") return "warn";
  if (status === "CONTRADICTED" || status === "UNSUPPORTED") return "bad";
  return "neutral";
}

function plainText(text: string) { return text.replace(/[*_`#]+/g, "").replace(/\s+/g, " ").trim(); }

function humanize(code: string) { return code.replaceAll("_", " ").toLowerCase(); }

function percent(value?: number | null) { return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value * 100)}%` : "—"; }

function ReliabilityPanel({ candidate }: { candidate: Candidate }) {
  const values = Object.values(candidate.claim_values ?? {});
  const metrics = [
    ["Visual evidence · mean vᵢ", values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null, "no verifier output"],
    ["Candidate agreement · Aⱼ", candidate.agreement_available ? candidate.agreement : null, "n/a (single candidate)"],
    ["Token confidence · pⱼ", candidate.probability_available ? candidate.probability ?? null : null, "n/a (API model)"],
  ] as const;
  return <Panel className="p-5"><div className="flex items-center justify-between"><Eyebrow>Toolkit reliability</Eyebrow><Activity size={14} className="text-violet-200/70"/></div><div className="mt-4 flex items-end gap-2"><span className="text-5xl font-semibold tracking-[-.07em] text-zinc-100">{percent(candidate.reliability)}</span><span className="mono mb-1 text-[9px] uppercase tracking-widest text-zinc-600">measured</span></div><div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/[.06]"><motion.div initial={{ width: 0 }} animate={{ width: `${Math.max(0, Math.min(100, candidate.reliability * 100))}%` }} transition={{ duration: .8, ease: "easeOut" }} className="h-full rounded-full bg-gradient-to-r from-violet-400 to-cyan-200"/></div><div className="mt-5 space-y-3">{metrics.map(([label, value, missing]) => <div key={label} className="flex items-center justify-between border-t border-white/[.05] pt-3"><span className="text-xs text-zinc-500">{label}</span><span className="mono text-xs text-zinc-300">{value === null ? missing : percent(value)}</span></div>)}</div><p className="mt-4 text-[10px] leading-5 text-zinc-500">Rⱼ = λ₁·mean(vᵢ) + λ₂·pⱼ + λ₃·Aⱼ. Unavailable terms are never fabricated; their weight is redistributed to the available ones.</p></Panel>;
}

function DecisionPanel({ candidate }: { candidate: Candidate }) {
  const Icon = candidate.decision === "ACCEPT" || candidate.decision === "RERANK" ? ShieldCheck : candidate.decision === "ABSTAIN" ? CircleHelp : ShieldAlert;
  const copy: Record<string, string> = {
    ACCEPT: "All claims met the accept threshold.", RERANK: "The top candidate was below the reliability threshold; a reliable alternative was selected.",
    CORRECT: "Visual evidence supported evidence-backed corrections; verified content was left untouched.", ABSTAIN: "Some claims fall between thresholds or no candidate is reliable; flagged as uncertain rather than corrected.",
  };
  return <div className="flex gap-3 rounded-2xl border border-white/[.08] bg-white/[.025] p-4"><span className="grid size-9 shrink-0 place-items-center rounded-xl border border-white/[.07] bg-white/[.035]"><Icon size={16} className={candidate.decision === "ACCEPT" || candidate.decision === "RERANK" ? "text-emerald-200" : candidate.decision === "ABSTAIN" ? "text-amber-100" : "text-violet-200"}/></span><div><div className="flex items-center gap-2"><Eyebrow>Decision</Eyebrow><Pill tone={statusTone(candidate.decision)}>{candidate.decision}</Pill></div><p className="mt-2 text-xs leading-5 text-zinc-500">{candidate.decision_reason || copy[candidate.decision] || "Decision returned by the policy."}</p></div></div>;
}

function CorrectionPanel({ candidate }: { candidate: Candidate }) {
  const changed = candidate.corrected_text && candidate.corrected_text !== candidate.text;
  return <Panel className="p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><Eyebrow>Correction</Eyebrow><Sparkles size={13} className="text-violet-200/50"/></div>
    {changed ? <><p className="text-xs leading-7 text-zinc-400">{wordDiff(candidate.text, candidate.corrected_text).map((part, index) => part.kind === "same" ? <span key={index}>{part.text}</span> : part.kind === "del" ? <del key={index} className="rounded bg-rose-300/[.12] text-rose-200/80 decoration-rose-300/60">{part.text}</del> : <ins key={index} className="rounded bg-emerald-300/[.12] text-emerald-100 no-underline">{part.text}</ins>)}</p>
      <div className="mt-3 border-t border-white/[.06] pt-3 text-xs leading-6 text-emerald-100/90">{candidate.corrected_text}</div></>
      : <p className="text-xs leading-5 text-zinc-600">No evidence-backed correction was needed or possible. Uncertain claims are retained and flagged.</p>}
  </Panel>;
}

function ActionTable({ candidate }: { candidate: Candidate }) {
  const selectClaim = useWorkspace((state) => state.selectClaim);
  const selectedClaimId = useWorkspace((state) => state.selectedClaimId);
  const evidence = new Map(candidate.evidence.map((item) => [item.claim_id, item]));
  if (!candidate.claims.length) return <p className="text-xs text-zinc-600">No claims were extracted.</p>;
  return <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-left text-[11px]">
    <thead><tr className="border-b border-white/[.07] text-[9px] uppercase tracking-[.12em] text-zinc-600"><th className="py-2 pr-3 font-medium">Claim</th><th className="py-2 pr-3 font-medium">Verification result</th><th className="py-2 pr-3 font-medium">vᵢ</th><th className="py-2 font-medium">Action</th></tr></thead>
    <tbody>{candidate.claims.map((claim) => { const item = evidence.get(claim.id); const action = candidate.claim_actions?.[claim.id]; const crop = item?.region_crop;
      const active = selectedClaimId === claim.id;
      return <tr key={claim.id} className={`border-b border-white/[.04] align-top ${active ? "bg-violet-200/[.045]" : "hover:bg-white/[.02]"}`}>
        <td className="py-2.5 pr-3 text-zinc-200"><button type="button" onClick={() => selectClaim(active ? null : claim.id)} aria-pressed={active} aria-label={`Focus evidence for claim: ${claimLabel(claim)}`} className="rounded text-left hover:text-violet-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-300">{claimLabel(claim)}<span className="mono block text-[9px] text-zinc-500">{claim.id}</span></button></td>
        <td className="py-2.5 pr-3 text-zinc-500"><div className="flex gap-2">{crop && <img src={crop} alt={`Region crop for ${claim.subject}`} className="size-9 shrink-0 rounded object-cover"/>}<span>{item ? <><Pill tone={statusTone(item.status)}>{item.status}</Pill> <span className="ml-1">{item.explanation}</span></> : "not verified (ablation)"}</span></div></td>
        <td className="mono py-2.5 pr-3 text-zinc-300">{candidate.claim_values?.[claim.id] != null ? candidate.claim_values![claim.id].toFixed(2) : "—"}</td>
        <td className="py-2.5"><Pill tone={actionTone(action)}>{action ?? "—"}</Pill><div className="mt-1 text-[10px] text-zinc-500">{detailLabel(candidate.action_details?.[claim.id])}</div></td>
      </tr>; })}</tbody></table></div>;
}

function ImageViewer({ candidate }: { candidate: Candidate }) {
  const imageUrl = useWorkspace((state) => state.imageUrl);
  const selectedClaimId = useWorkspace((state) => state.selectedClaimId);
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 });
  const evidence = candidate.evidence;
  const selected = evidence.find((item) => item.claim_id === selectedClaimId);
  if (!imageUrl) return <EmptyState icon={<FileImage size={18}/>} title="Image unavailable" detail="This saved record contains analysis output but not the source image. Upload the image again to inspect bounding boxes."/>;
  return <div className="overflow-hidden rounded-2xl border border-white/[.08] bg-[#090a0d]">
    <div className="flex items-center justify-between border-b border-white/[.06] px-3 py-2.5"><Eyebrow>Evidence canvas</Eyebrow><span className="mono text-[9px] text-zinc-600">{selected ? selected.claim_id : "ALL REGIONS"}</span></div>
    <div className="relative"><TransformWrapper minScale={.6} maxScale={4} initialScale={1} centerOnInit limitToBounds={false}><div className="relative"><TransformComponent wrapperClass="!h-auto !w-full" contentClass="relative !h-auto !w-full">
      <div className="relative w-full"><img src={imageUrl} onLoad={(event) => setNaturalSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} alt="Uploaded image under visual verification" className="block h-auto w-full"/>
        <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 ${naturalSize.width || candidate.evidence.reduce((max, item) => Math.max(max, ...item.boxes.map((box) => box[2] ?? 0)), 0) || 1} ${naturalSize.height || candidate.evidence.reduce((max, item) => Math.max(max, ...item.boxes.map((box) => box[3] ?? 0)), 0) || 1}`} preserveAspectRatio="none" aria-hidden="true">
          {evidence.flatMap((item) => item.boxes.map((box, index) => {
            const active = item.claim_id === selectedClaimId;
            const color = item.status === "SUPPORTED" ? "#79d6a1" : item.status === "AMBIGUOUS" ? "#e6bd75" : "#f27c84";
            return <g key={`${item.claim_id}-${index}`} opacity={selectedClaimId && !active ? .18 : .95}><rect x={box[0]} y={box[1]} width={box[2] - box[0]} height={box[3] - box[1]} fill="none" stroke={color} strokeWidth={active ? 4 : 2}/>{active && <text x={box[0] + 4} y={Math.max(13, box[1] - 6)} fill={color} fontSize="13" fontFamily="monospace">{item.claim_id} · {item.status} · {percent(item.confidence)}</text>}</g>;
          }))}
        </svg>
      </div>
    </TransformComponent></div><div className="absolute bottom-3 right-3 z-10 rounded-lg border border-white/10 bg-black/65 px-2 py-1 mono text-[9px] text-zinc-500">Scroll / pinch to zoom · drag to pan</div></TransformWrapper></div>
    <div className="flex flex-wrap items-center gap-3 border-t border-white/[.06] px-3 py-2.5">{[["#79d6a1", "Supported"], ["#e6bd75", "Ambiguous"], ["#f27c84", "Contradicted / unsupported"]].map(([color, label]) => <span key={label} className="flex items-center gap-1.5 text-[9px] text-zinc-600"><i className="size-1.5 rounded-sm" style={{ backgroundColor: color }}/>{label}</span>)}</div>
  </div>;
}

function ClaimList({ candidate, compact = false }: { candidate: Candidate; compact?: boolean }) {
  const selectedClaimId = useWorkspace((state) => state.selectedClaimId);
  const selectClaim = useWorkspace((state) => state.selectClaim);
  const records = candidate.claims.map((claim) => ({ claim, evidence: candidate.evidence.find((item) => item.claim_id === claim.id) }));
  if (!records.length) return <EmptyState icon={<ScanEye size={18}/>} title="No claims extracted" detail="The response did not produce typed claims for inspection."/>;
  return <div className="space-y-2">{records.map(({ claim, evidence }) => <button key={claim.id} onClick={() => selectClaim(selectedClaimId === claim.id ? null : claim.id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedClaimId === claim.id ? "border-violet-200/30 bg-violet-200/[.055]" : "border-white/[.06] bg-white/[.012] hover:border-white/[.12] hover:bg-white/[.025]"}`} aria-pressed={selectedClaimId === claim.id}>
    <div className="flex items-start justify-between gap-2"><div><span className="mono mr-2 text-[9px] text-violet-200/80">{claim.id}</span><span className="text-xs font-medium text-zinc-200">{claim.subject}</span></div><div className="flex gap-1"><Pill tone={statusTone(evidence?.status)}>{evidence?.status ?? "NO EVIDENCE"}</Pill>{candidate.claim_actions?.[claim.id] && <Pill tone={actionTone(candidate.claim_actions[claim.id])}>{candidate.claim_actions[claim.id]}</Pill>}</div></div>
    <div className="mt-1.5 text-[11px] text-zinc-500">{claim.attribute ? `${claim.attribute} · ` : ""}{claim.value ?? claim.type}{claim.object ? ` → ${claim.object}` : ""}</div>
    {!compact && evidence && selectedClaimId === claim.id && <div className="mt-3 border-t border-white/[.07] pt-3 text-[11px] leading-5 text-zinc-500"><div className="flex justify-between"><span>Claim score</span><span className="mono text-zinc-300">{percent(evidence.score)}</span></div>{evidence.verified_value != null && <div className="mt-1 flex justify-between"><span>Verified value</span><span className="text-zinc-300">{evidence.verified_value}</span></div>}<p className="mt-2">{evidence.explanation || "No explanation was returned."}</p><span className="mt-2 inline-block text-violet-200/80">Click to focus image and graph evidence →</span></div>}
  </button>)}</div>;
}

function AnalysisWorkspace() {
  const analysis = useWorkspace((state) => state.analysis);
  const activeCandidate = useWorkspace((state) => state.activeCandidate);
  const setAnalysis = useWorkspace((state) => state.setAnalysis);
  const setCandidate = useWorkspace((state) => state.setCandidate);
  const configQuery = useQuery({ queryKey: ["config"], queryFn: getConfig });
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [zoomImage, setZoomImage] = useState<string | null>(null);
  const { register, handleSubmit, watch, reset, formState: { errors } } = useForm<AnalysisForm>({
    resolver: zodResolver(formSchema), defaultValues: { query: "Describe the objects and their colors.", provider: "", candidateCount: 3, manualResponse: "", verificationWeight: .6, agreementWeight: .2 },
  });
  useEffect(() => {
    if (!configQuery.data) return;
    reset({ query: "Describe the objects and their colors.", provider: configQuery.data.provider, candidateCount: configQuery.data.defaults.candidate_count, manualResponse: "", verificationWeight: configQuery.data.defaults.verification_weight, agreementWeight: configQuery.data.defaults.agreement_weight });
  }, [configQuery.data, reset]);
  const thresholds = configQuery.data?.defaults.thresholds ?? {};
  const mutation = useMutation({ mutationFn: async (values: AnalysisForm) => {
    if (!file) throw new Error("Choose an image to analyze.");
    return analyzeImage({ file, query: values.query, provider: values.provider, candidateCount: values.candidateCount, manualResponse: values.manualResponse, verificationWeight: values.verificationWeight, agreementWeight: values.agreementWeight });
  }, onSuccess: (result) => { const url = zoomImage ?? URL.createObjectURL(file!); setAnalysis(result.analysis, url); setZoomImage(url); toast.success("Analysis complete", { description: `${result.analysis.candidates.length} real candidate(s) verified.` }); }, onError: (error) => toast.error("Verification failed", { description: error.message }) });
  const best = analysis?.candidates[activeCandidate] ?? analysis?.candidates[0];
  const chooseFile = (next?: File) => { if (!next) return; if (!next.type.startsWith("image/")) { toast.error("Choose a supported image file."); return; } if (next.size > 15 * 1024 * 1024) { toast.error("Image exceeds the 15 MB upload limit."); return; } if (zoomImage) URL.revokeObjectURL(zoomImage); useWorkspace.getState().clear(); setFile(next); const url = URL.createObjectURL(next); setZoomImage(url); };
  const submit = handleSubmit((values) => mutation.mutate(values));

  return <>
    <PageHeading eyebrow="Research workspace / 01" title="Verify an image, claim by claim." detail="Grounding DINO localizes claimed objects; crop-level probes check attributes on the same region." right={best ? <Pill tone="good"><span className="flex items-center gap-1"><span className="size-1.5 rounded-full bg-emerald-300"/> Pipeline connected</span></Pill> : <Pill>Ready for image</Pill>}/>
    <form onSubmit={submit} className="grid items-start gap-4 xl:grid-cols-[minmax(300px,.92fr)_minmax(340px,1.06fr)_minmax(280px,.82fr)]">
      <div className="space-y-4">
        <Panel className="p-4 sm:p-5"><div className="mb-4 flex items-center justify-between"><Eyebrow>01 / Image input</Eyebrow>{file && <button type="button" onClick={() => { setFile(null); setZoomImage(null); }} className="text-zinc-600 hover:text-zinc-300" aria-label="Remove image"><X size={14}/></button>}</div>
          <label onDragOver={(event) => { event.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={(event) => { event.preventDefault(); setDrag(false); chooseFile(event.dataTransfer.files[0]); }} className={`relative flex min-h-48 cursor-pointer flex-col items-center justify-center overflow-hidden rounded-xl border border-dashed transition ${drag ? "border-violet-200/50 bg-violet-200/[.07]" : "border-white/[.12] bg-white/[.012] hover:border-white/20 hover:bg-white/[.025]"}`}>
            {zoomImage ? <img src={zoomImage} alt="Selected image preview" className="absolute inset-0 h-full w-full object-contain"/> : <><span className="mb-3 grid size-10 place-items-center rounded-xl border border-white/[.09] bg-white/[.035] text-violet-200"><ImagePlus size={17}/></span><span className="text-xs font-medium text-zinc-300">Drop an image here</span><span className="mt-1 text-[10px] text-zinc-600">or browse · PNG, JPG, WEBP · up to 15 MB</span></>}
            <input type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={(event) => { chooseFile(event.target.files?.[0]); event.currentTarget.value = ""; }} aria-label="Choose image file"/>
            {zoomImage && <span className="absolute bottom-2 left-2 rounded-md bg-black/70 px-2 py-1 mono text-[9px] text-zinc-300">{file?.name ?? "Uploaded image"}</span>}
          </label>
        </Panel>
        <Panel className="p-4 sm:p-5"><div className="mb-4 flex items-center justify-between"><Eyebrow>02 / Analysis controls</Eyebrow><SlidersHorizontal size={14} className="text-zinc-600"/></div>
          <label className="mb-1.5 block text-xs text-zinc-500" htmlFor="query">Question</label><textarea id="query" {...register("query")} rows={2} className="w-full resize-y rounded-xl border border-white/[.09] bg-black/20 px-3 py-2.5 text-sm leading-5 text-zinc-200 placeholder:text-zinc-600 focus:border-violet-200/30 focus:outline-none"/>{errors.query && <p className="mt-1 text-xs text-rose-300">{errors.query.message}</p>}
          <div className="mt-4 grid grid-cols-2 gap-3"><label className="text-xs text-zinc-500">Generator model<select {...register("provider")} className="mt-1.5 w-full rounded-lg border border-white/[.09] bg-[#111318] px-2.5 py-2 text-sm text-zinc-200" disabled={configQuery.isPending}>{(configQuery.data?.models ?? []).map((item) => <option key={item.id} value={item.id}>{item.model}</option>)}</select></label><label className="text-xs text-zinc-500">Candidates<select {...register("candidateCount", { valueAsNumber: true })} className="mt-1.5 w-full rounded-lg border border-white/[.09] bg-[#111318] px-2.5 py-2 text-sm text-zinc-200">{[1,2,3].map((n) => <option key={n} value={n}>{n}</option>)}</select></label></div><p className="mt-3 text-[11px] leading-5 text-zinc-600">Visual verifier: Grounding DINO object grounding + CLIP attribute checks on grounded crops. No verifier LLM is called.</p>
          <details className="group mt-4 border-t border-white/[.06] pt-3"><summary className="flex cursor-pointer list-none items-center justify-between text-xs text-zinc-400 hover:text-zinc-200">Reliability policy <ChevronDown size={15} className="transition group-open:rotate-180"/></summary><div className="mt-4 grid grid-cols-2 gap-x-3 gap-y-4">{([["verificationWeight","λ₁ visual"],["agreementWeight","λ₃ agreement"]] as const).map(([key,label]) => <label key={key} className="text-[11px] text-zinc-600">{label}<span className="mono float-right text-zinc-400">{Number(watch(key)).toFixed(2)}</span><input type="range" min="0" max="1" step=".05" {...register(key,{valueAsNumber:true})} className="mt-2 w-full accent-violet-300"/></label>)}</div><div className="mt-4 space-y-1 text-[11px] text-zinc-600">{Object.entries(thresholds).map(([kind, t]) => <div key={kind} className="flex justify-between"><span>{kind}: correct ≤ lo · accept ≥ hi</span><span className="mono text-zinc-400">{t.lo.toFixed(2)} / {t.hi.toFixed(2)}</span></div>)}</div><p className="mt-3 text-[11px] leading-5 text-zinc-500">Thresholds come from config/config.yaml{configQuery.data?.defaults.tuned ? " (tuned on the held-out POPE split)" : ""}. Token confidence pⱼ is only available for the local hf-local model.</p></details>
          <details className="mt-3 border-t border-white/[.06] pt-3"><summary className="cursor-pointer text-xs text-zinc-400 hover:text-zinc-200">Controlled candidate override</summary><textarea {...register("manualResponse")} rows={3} placeholder="Optional. Separate multiple candidate texts with |||" className="mt-3 w-full rounded-lg border border-white/[.09] bg-black/20 px-3 py-2 text-xs leading-5 text-zinc-300 placeholder:text-zinc-600 focus:outline-none"/></details>
          <Button type="submit" className="mt-5 h-11 w-full" disabled={!file || mutation.isPending}>{mutation.isPending ? <><LoaderCircle size={15} className="animate-spin"/> Running verifier…</> : <>Run reliability analysis <ArrowRight size={14}/></>}</Button>
          {mutation.isPending && <p className="mt-3 flex items-center gap-2 text-xs text-zinc-600"><span className="size-1.5 animate-pulse rounded-full bg-violet-300"/>Waiting for the existing pipeline to complete. Backend stage-level progress is not exposed.</p>}
        </Panel>
      </div>

      <div className="space-y-4">
        <Panel className="p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><Eyebrow>03 / Visual evidence</Eyebrow>{best && <Pill tone="violet">{best.evidence.length} evidence records</Pill>}</div>{best ? <ImageViewer candidate={best}/> : <EmptyState icon={<ScanEye size={18}/>} title="Evidence canvas" detail="Run an analysis to see verified boxes and claim-linked highlighting."/>}</Panel>
        <Panel className="p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><Eyebrow>04 / Claim inspector</Eyebrow>{best && <span className="mono text-[9px] text-zinc-600">{best.claims.length} CLAIMS</span>}</div>{best ? <ClaimList candidate={best}/> : <EmptyState icon={<Activity size={18}/>} title="Claims will appear here" detail="Typed claims are extracted from the model response after analysis."/>}</Panel>
      </div>

      <div className="space-y-4">
        {best ? <>
          {analysis!.candidates.length > 1 && <Panel className="p-4"><div className="mb-3 flex items-center justify-between"><Eyebrow>Candidate selection</Eyebrow><span className="mono text-[9px] text-zinc-600">{analysis!.candidates.length} TOTAL</span></div><select value={activeCandidate} onChange={(event) => setCandidate(Number(event.target.value))} className="w-full rounded-lg border border-white/[.09] bg-[#111318] px-3 py-2 text-xs text-zinc-200">{analysis!.candidates.map((candidate,index) => <option key={candidate.id} value={index}>{candidate.id}{candidate.selected ? " (selected)" : ""} · {candidate.decision} · R {percent(candidate.reliability)}</option>)}</select></Panel>}
          <ReliabilityPanel candidate={best}/><DecisionPanel candidate={best}/>
          <Panel className="p-4 sm:p-5"><div className="flex items-center justify-between"><Eyebrow>Original model response</Eyebrow><Pill>{best.model}</Pill></div><p className="mt-4 whitespace-pre-line text-sm leading-7 text-zinc-300">{best.original_response ?? best.text}</p><p className="mt-3 mono text-[9px] text-zinc-500">{analysis!.experiment_id ? `RUN ${String(analysis!.experiment_id).padStart(4, "0")} · ` : ""}Generator model: {best.model || "unavailable"} · visual verification: Grounding DINO + CLIP region probe{best.latency_ms != null ? ` · ${(best.latency_ms / 1000).toFixed(1)}s` : ""} · {best.id} · agreement {percent(best.agreement)}</p></Panel>
          <CorrectionPanel candidate={best}/>
        </> : <Panel className="p-5"><EmptyState icon={<ShieldCheck size={18}/>} title="Awaiting verification" detail="Reliability and decision panels will show values returned by the backend, never simulated scores."/></Panel>}
      </div>
    </form>
    {best && <Panel className="mt-4 p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><div><Eyebrow>Claim verification and action</Eyebrow><p className="mt-1 text-[10px] text-zinc-600">Per-claim decision policy (paper Table IV): accept ≥ hi · correct ≤ lo with evidence · otherwise flag.</p></div><Pill tone="violet">{best.claims.length} claims</Pill></div><ActionTable candidate={best}/></Panel>}
    {best && <Panel className="mt-4 overflow-hidden p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><div><Eyebrow>Claim graph</Eyebrow><p className="mt-1 text-[10px] text-zinc-600">Select a node to focus the matching claim and its image evidence.</p></div><Pill tone="violet">backend graph data</Pill></div><ClaimGraph graph={best.graph} selectedCandidate={best}/></Panel>}
  </>;
}

function ClaimsPage() {
  const analysis = useWorkspace((state) => state.analysis); const index = useWorkspace((state) => state.activeCandidate); const candidate = analysis?.candidates[index] ?? analysis?.candidates[0];
  return <><PageHeading eyebrow="Claim graph / typed extraction" title="A response, decomposed." detail="Select a claim to highlight it in the graph and inspect its corresponding evidence."/>{candidate ? <><Panel className="mb-4 p-4 sm:p-5"><Eyebrow>Verification and action per claim</Eyebrow><div className="mt-3"><ActionTable candidate={candidate}/></div></Panel><div className="grid gap-4 xl:grid-cols-[.75fr_1.25fr]"><Panel className="p-4 sm:p-5"><Eyebrow>Extracted claims</Eyebrow><div className="mt-4"><ClaimList candidate={candidate}/></div></Panel><Panel className="p-4 sm:p-5"><Eyebrow>Claim graph</Eyebrow><div className="mt-3"><ClaimGraph graph={candidate.graph} selectedCandidate={candidate}/></div></Panel></div></> : <EmptyState icon={<Activity size={18}/>} title="No analysis to inspect" detail="Run an image analysis first. Claim IDs, graph edges, and statuses come from real backend output." action={<Link href="/analyze"><Button>Go to Analyze <ArrowRight size={14}/></Button></Link>}/>}</>;
}

function EvidencePage() {
  const analysis = useWorkspace((state) => state.analysis);
  const index = useWorkspace((state) => state.activeCandidate);
  const candidate = analysis?.candidates[index] ?? analysis?.candidates[0];
  const selectClaim = useWorkspace((state) => state.selectClaim);
  const selectedClaimId = useWorkspace((state) => state.selectedClaimId);
  return <>
    <PageHeading eyebrow="Visual verification / evidence" title="Trace the visual support." detail="Every status and score below is returned by the verification backend; missing evidence stays explicitly unavailable." />
    {candidate ? <div className="grid items-start gap-4 xl:grid-cols-[1.1fr_.9fr]">
      <Panel className="p-4 xl:sticky xl:top-24"><ImageViewer candidate={candidate}/></Panel>
      <div className="space-y-2">{candidate.evidence.map((item: Evidence) => { const claim = candidate.claims.find((entry) => entry.id === item.claim_id); const active = selectedClaimId === item.claim_id;
        return <button key={item.claim_id} onClick={() => selectClaim(active ? null : item.claim_id)} aria-pressed={active} className={`surface block w-full rounded-2xl p-4 text-left transition ${active ? "!border-violet-200/30 bg-violet-200/[.045]" : "hover:border-white/[.16]"}`}>
        <div className="flex items-start justify-between gap-3"><div className="min-w-0"><Eyebrow>{item.claim_id} / {item.diagnosis ? humanize(item.diagnosis) : "verification"}</Eyebrow><p className="mt-2 text-sm font-medium text-zinc-200">{claim ? claimLabel(claim) : "Claim details unavailable"}</p>{claim?.text && <p className="mt-1 text-[11px] italic leading-5 text-zinc-500">“{plainText(claim.text)}”</p>}</div><Pill tone={statusTone(item.status)}>{item.status}</Pill></div>
        <p className="mt-3 text-[11px] leading-5 text-zinc-500">{item.explanation || "Visual evidence explanation unavailable."}</p>
        <div className="mt-3 flex flex-wrap gap-2">{item.source?.length ? item.source.map((source) => <Pill key={source}>{source}</Pill>) : <Pill>Sources unavailable</Pill>}<Pill tone="violet">Score {percent(item.score)}</Pill>{item.confidence > 0 && <Pill>Verifier estimate · uncalibrated {percent(item.confidence)}</Pill>}</div>
        {item.signals && Object.keys(item.signals).length > 0 && <details onClick={(event) => event.stopPropagation()} className="mt-3 border-t border-white/[.06] pt-3"><summary className="cursor-pointer text-[10px] text-zinc-600">Inspect returned signals</summary><pre className="mt-2 overflow-auto text-[9px] leading-4 text-zinc-500">{JSON.stringify(item.signals, null, 2)}</pre></details>}
      </button>; })}</div>
    </div> : <EmptyState icon={<ScanEye size={18}/>} title="Visual evidence unavailable" detail="Run an analysis to inspect claim-linked boxes, verifier sources, and contradiction signals." action={<Link href="/analyze"><Button>Start an analysis</Button></Link>} />}
  </>;
}

function CandidatesPage() {
  const analysis = useWorkspace((state) => state.analysis); const setCandidate = useWorkspace((state) => state.setCandidate);
  const candidates = analysis?.candidates ?? [];
  const chart = candidates.map((item) => ({ name: `${item.id}${item.selected ? " ✓" : ""}`, reliability: Math.round(item.reliability * 100), agreement: item.agreement_available ? Math.round(item.agreement * 100) : 0 }));
  return <><PageHeading eyebrow="Candidate comparison / actual run" title="Compare what the model said." detail="Candidates are ordered and scored by the existing verifier. Every chart point corresponds to a real returned candidate."/>{candidates.length ? <><Panel className="p-5"><Eyebrow>Measured comparison · percent</Eyebrow><CandidateChart data={chart}/></Panel><div className="mt-4 grid gap-3 lg:grid-cols-2">{candidates.map((candidate,index) => <button key={candidate.id} onClick={() => setCandidate(index)} className={`surface rounded-2xl p-5 text-left transition ${candidate.selected ? "border-violet-200/25" : "hover:border-white/15"}`}><div className="flex items-start justify-between"><div><Eyebrow>{candidate.id}{candidate.generation_strategy ? ` · ${candidate.generation_strategy}` : ""}</Eyebrow><h3 className="mt-2 text-2xl font-medium tracking-[-.05em]">R {percent(candidate.reliability)}</h3></div><div className="flex flex-col items-end gap-1">{candidate.selected && <Pill tone="violet">selected</Pill>}<Pill tone={statusTone(candidate.decision)}>{candidate.decision}</Pill></div></div><p className="mt-3 line-clamp-3 text-xs leading-6 text-zinc-400">{candidate.text}</p>{candidate.selected && candidate.decision_reason && <p className="mt-2 text-[10px] leading-5 text-violet-200/70">{candidate.decision_reason}</p>}<div className="mt-4 flex flex-wrap gap-2"><Pill>{candidate.claims.length} claims</Pill><Pill>agreement {candidate.agreement_available ? percent(candidate.agreement) : "n/a"}</Pill><Pill>pⱼ {candidate.probability_available ? percent(candidate.probability) : "n/a (API model)"}</Pill></div><div className="mt-4 border-t border-white/[.06] pt-3 text-[10px] text-zinc-600">{candidate.diagnosis.length ? candidate.diagnosis.map(humanize).join(" · ") : "No diagnosis returned"}</div></button>)}</div></> : <EmptyState icon={<Layers3 size={18}/>} title="No candidates to compare" detail="Run an analysis with multiple candidates or provide candidate overrides separated by |||." action={<Link href="/analyze"><Button>Run analysis</Button></Link>}/>}</>;
}

const pct = (value?: number | null) => (typeof value === "number" ? (value * 100).toFixed(1) : "—");
const CHAIR_ORDER = ["base_vlm", "full_toolkit", "n_equals_1", "no_reliability_scoring", "no_attribute_binding"];

function MetricTable({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-[11px]"><thead><tr className="border-b border-white/[.07] text-[9px] uppercase tracking-[.12em] text-zinc-600">{head.map((h) => <th key={h} className="py-2 pr-3 font-medium">{h}</th>)}</tr></thead>
    <tbody>{rows.map((row, index) => <tr key={index} className="border-b border-white/[.04]">{row.map((cell, j) => <td key={j} className={`py-2 pr-3 ${j < 2 ? "text-zinc-300" : "mono text-zinc-400"}`}>{cell}</td>)}</tr>)}</tbody></table></div>;
}

function EvaluationPage() {
  const query = useQuery({ queryKey: ["benchmarks"], queryFn: getBenchmarks });
  const results = query.data?.results;
  const pope = results?.pope ?? {}; const chair = results?.chair ?? {};
  const popeRows = ["base_vlm", "full_toolkit", ...Object.keys(pope).filter((k) => k !== "base_vlm" && k !== "full_toolkit")].flatMap((name) =>
    Object.entries(pope[name] ?? {}).filter(([, m]) => m.status === "EVALUATED").map(([split, m]) => [name, split, m.sample_count, pct(m.accuracy), pct(m.precision), pct(m.recall), pct(m.f1), pct(m.yes_ratio), pct(m.abstention_rate)]));
  const chairRows = [...CHAIR_ORDER.filter((k) => chair[k]), ...Object.keys(chair).filter((k) => !CHAIR_ORDER.includes(k))].map((name) => {
    const m = chair[name]; const lat = results?.latency?.[name];
    return [name, m.sample_count, pct(m.CHAIR_S), pct(m.CHAIR_I), pct(m.object_recall), m.avg_length.toFixed(1), lat?.ratio != null ? `${lat.ratio}×` : "—"];
  });
  const meta = results?.meta;
  return <><PageHeading eyebrow="Evaluation / measured benchmark runs" title="Benchmarks, as measured." detail="POPE (object existence) and CHAIR (caption hallucination) from processed benchmark rows. No targets or synthetic scores are shown."/>
    {query.isError && <p role="alert" className="mb-3 text-xs text-rose-300">Could not reach the benchmark service: {(query.error as Error).message}</p>}
    {!results || (!popeRows.length && !chairRows.length) ? <EmptyState icon={<Database size={18}/>} title="No benchmark run processed yet" detail={query.data?.message ?? "Run the Kaggle notebook, download results, then python -m evaluation.run_benchmarks."}/> : <div className="space-y-4">
      {meta && <Panel className="p-4"><div className="flex flex-wrap gap-2"><Pill tone="violet">{meta.model ?? "model ?"}</Pill><Pill>{meta.precision ?? "precision ?"}</Pill><Pill>{meta.hardware ?? "hardware ?"}</Pill><Pill tone={meta.tuned ? "good" : "warn"}>{meta.tuned ? "thresholds tuned on held-out split" : "default thresholds"}</Pill>{query.data?.timestamp && <Pill>{query.data.timestamp.slice(0, 16).replace("T", " ")} UTC</Pill>}</div></Panel>}
      {popeRows.length > 0 && <Panel className="p-5"><Eyebrow>POPE · object existence</Eyebrow><div className="mt-3"><MetricTable head={["Variant", "Split", "N", "Acc", "Prec", "Rec", "F1", "Yes %", "Abstain %"]} rows={popeRows}/></div></Panel>}
      {chairRows.length > 0 && <Panel className="p-5"><Eyebrow>CHAIR · caption hallucination (lower is better) and object recall</Eyebrow><div className="mt-3"><MetricTable head={["Variant", "N", "CHAIR_S", "CHAIR_I", "Recall", "Avg words", "Latency"]} rows={chairRows}/></div></Panel>}
      <p className="text-[10px] leading-5 text-zinc-600">POPE and CHAIR measure object hallucination only; attribute-binding correction is shown qualitatively in the Analyze view. POPE uses 450 images per split because 50 are held out for threshold tuning.</p>
    </div>}</>;
}

function ExperimentsPage() {
  const list = useQuery({ queryKey: ["history"], queryFn: getHistory });
  const [active, setActive] = useState<number | null>(null);
  const item = useQuery({ queryKey: ["history", active], queryFn: () => getHistoryItem(active!), enabled: active !== null });
  const open = (row: HistorySummary) => setActive(row.id);
  return <><PageHeading eyebrow="Local run history / SQLite" title="Every run, traceable." detail="Experiment records are loaded from the existing database and opened without changing its schema."/>{list.isPending ? <Panel className="animate-pulse p-7"><div className="h-4 w-48 rounded bg-white/[.05]"/><div className="mt-5 h-24 rounded-xl bg-white/[.03]"/></Panel> : list.isError ? <EmptyState icon={<Database size={18}/>} title="History service unavailable" detail={(list.error as Error).message}/> : !list.data?.length ? <EmptyState icon={<Clock3 size={18}/>} title="No experiments yet" detail="Completed analyses will be stored in the existing SQLite history."/> : <div className="grid gap-4 xl:grid-cols-[.8fr_1.2fr]"><Panel className="overflow-hidden"><div className="border-b border-white/[.06] px-4 py-3"><Eyebrow>Recent experiments</Eyebrow></div><div className="max-h-[640px] overflow-auto">{list.data.map((row) => <button key={row.id} onClick={() => open(row)} className={`block w-full border-b border-white/[.05] px-4 py-4 text-left transition hover:bg-white/[.025] ${active === row.id ? "bg-violet-200/[.045]" : ""}`}><div className="flex items-center justify-between"><span className="mono text-[9px] text-zinc-600">RUN {String(row.id).padStart(4,"0")}</span><span className="mono text-[9px] text-zinc-500">{row.created_at}</span></div><p className="mt-2 line-clamp-2 text-xs leading-5 text-zinc-300">{row.query}</p></button>)}</div></Panel><Panel className="min-h-72 p-5">{active !== null && item.isPending ? <div className="animate-pulse text-xs text-zinc-500">Loading experiment…</div> : item.data ? <><div className="flex items-center justify-between"><Eyebrow>Run {String(item.data.id).padStart(4,"0")} · {item.data.created_at}</Eyebrow><a href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(item.data.payload,null,2))}`} download={`experiment-${item.data.id}.json`} className="inline-flex items-center gap-1.5 text-[10px] text-zinc-500 hover:text-zinc-200"><Download size={13}/> Export JSON</a></div><h2 className="mt-3 text-lg font-medium tracking-[-.04em]">{item.data.query}</h2><div className="mt-5 space-y-3">{item.data.payload.candidates.map((candidate) => <div key={candidate.id} className="rounded-xl border border-white/[.07] bg-white/[.015] p-4"><div className="flex items-center justify-between"><span className="mono text-[9px] text-zinc-600">{candidate.id} · {candidate.model}</span><Pill tone={statusTone(candidate.decision)}>{candidate.decision} · {percent(candidate.reliability)}</Pill></div><p className="mt-3 text-xs leading-6 text-zinc-300">{candidate.text}</p><p className="mt-2 text-[10px] text-zinc-600">{candidate.claims.length} claims · {candidate.evidence.length} evidence records · image not persisted</p></div>)}</div></> : <EmptyState icon={<Clock3 size={18}/>} title="Select an experiment" detail="Open a run to inspect its response, claims, and saved evidence."/>}</Panel></div>}</>;
}

export function WorkspaceShell({ section }: { section: string }) {
  const [eyebrow,title,detail] = titles[section];
  const pages: Record<string, () => React.ReactNode> = { analyze: AnalysisWorkspace, claims: ClaimsPage, evidence: EvidencePage, candidates: CandidatesPage, evaluation: EvaluationPage, experiments: ExperimentsPage };
  const Page = pages[section];
  return <main className="min-h-screen bg-[#0b0c0f]"><SiteHeader/><div className="mx-auto max-w-[1480px] px-4 pb-20 pt-28 sm:px-7 lg:px-10"><nav aria-label="Workspace sections" className="mb-6 flex gap-1 overflow-x-auto border-b border-white/[.06] pb-3 hide-scrollbar xl:hidden">{Object.entries(titles).map(([key,[label]]) => <Link key={key} href={`/${key}`} aria-current={section === key ? "page" : undefined} className={`whitespace-nowrap rounded-lg px-3 py-2 text-[11px] transition ${section === key ? "bg-white/[.07] text-zinc-100" : "text-zinc-500 hover:text-zinc-200"}`}>{label.split(" / ")[1]}</Link>)}</nav><Page/></div><footer className="border-t border-white/[.05] px-4 py-5 text-center"><span className="mono text-[9px] uppercase tracking-[.15em] text-zinc-600">Local-first · evidence-linked · uncertainty-aware</span></footer></main>;
}
