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
import { Activity, ArrowRight, Check, ChevronDown, CircleHelp, Clock3, Database, Download, FileImage, ImagePlus, Layers3, LoaderCircle, ScanEye, ShieldAlert, ShieldCheck, SlidersHorizontal, Sparkles, X } from "lucide-react";
import { TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";
import { toast } from "sonner";
import { SiteHeader } from "@/components/site-header";
import { Button, EmptyState, Eyebrow, PageHeading, Panel, Pill } from "@/components/ui";
import { analyzeImage, getConfig, getEvaluation, getHistory, getHistoryItem } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import type { Candidate, Evidence, HistorySummary } from "@/lib/types";
import { ClaimGraph } from "@/components/claim-graph";

const formSchema = z.object({
  query: z.string().min(1, "Enter a question for the model.").max(2000),
  provider: z.string().min(1, "Select a provider."),
  candidateCount: z.number().int().min(1).max(3),
  manualResponse: z.string().max(12000),
  verificationWeight: z.number().min(0).max(1), agreementWeight: z.number().min(0).max(1),
  highThreshold: z.number().min(.5).max(1), lowThreshold: z.number().min(0).max(.5),
});
type AnalysisForm = z.infer<typeof formSchema>;
const CandidateChart = dynamic(() => import("@/components/candidate-chart"), { ssr: false, loading: () => <div className="grid h-64 place-items-center text-[10px] text-zinc-600">Loading comparison chart…</div> });

const titles: Record<string, [string, string, string]> = {
  analyze: ["01 / Analyze", "Verify an image, claim by claim.", "Run the existing VLM reliability pipeline and inspect its real output."],
  claims: ["02 / Claims", "A response, decomposed.", "Inspect typed claims and the graph structure extracted by the current backend."],
  evidence: ["03 / Evidence", "Trace the visual support.", "Review Grounding DINO regions, crop-level attribute evidence, contradictions, and uncertainty."],
  candidates: ["04 / Candidates", "Compare what the model said.", "Rank the actual candidates returned by this run; no synthetic comparison scores."],
  evaluation: ["05 / Evaluation", "A research view for labelled data.", "Metrics only appear when labelled evaluation records exist."],
  experiments: ["06 / Experiments", "Every run, traceable.", "Browse and reopen records saved by the existing SQLite experiment history."],
};

function statusTone(status?: string): "good" | "warn" | "bad" | "neutral" {
  if (status === "SUPPORTED" || status === "ACCEPT" || status === "RERANK") return "good";
  if (status === "AMBIGUOUS" || status === "ABSTAIN" || status === "CORRECT") return "warn";
  if (status === "CONTRADICTED" || status === "UNSUPPORTED") return "bad";
  return "neutral";
}

function percent(value?: number | null) { return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value * 100)}%` : "—"; }

function ReliabilityPanel({ candidate }: { candidate: Candidate }) {
  const metrics = [
    ["Visual evidence", candidate.evidence.length ? candidate.evidence.reduce((sum, item) => sum + item.score, 0) / candidate.evidence.length : null],
    ["Candidate agreement", candidate.agreement],
    ["Model probability", candidate.probability_available ? candidate.probability ?? null : null],
  ] as const;
  return <Panel className="p-5"><div className="flex items-center justify-between"><Eyebrow>Toolkit reliability</Eyebrow><Activity size={14} className="text-violet-200/70"/></div><div className="mt-4 flex items-end gap-2"><span className="text-5xl font-semibold tracking-[-.07em] text-zinc-100">{percent(candidate.reliability)}</span><span className="mono mb-1 text-[9px] uppercase tracking-widest text-zinc-600">measured</span></div><div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/[.06]"><motion.div initial={{ width: 0 }} animate={{ width: `${Math.max(0, Math.min(100, candidate.reliability * 100))}%` }} transition={{ duration: .8, ease: "easeOut" }} className="h-full rounded-full bg-gradient-to-r from-violet-400 to-cyan-200"/></div><div className="mt-5 space-y-3">{metrics.map(([label, value]) => <div key={label} className="flex items-center justify-between border-t border-white/[.05] pt-3"><span className="text-xs text-zinc-500">{label}</span><span className="mono text-xs text-zinc-300">{value === null ? "Unavailable" : percent(value)}</span></div>)}</div><p className="mt-4 text-[10px] leading-5 text-zinc-700">Provider token probabilities are unavailable here, so none are fabricated; their configured weight is redistributed to visual verification.</p></Panel>;
}

function DecisionPanel({ candidate }: { candidate: Candidate }) {
  const Icon = candidate.decision === "ACCEPT" || candidate.decision === "RERANK" ? ShieldCheck : candidate.decision === "ABSTAIN" ? CircleHelp : ShieldAlert;
  const copy: Record<string, string> = {
    ACCEPT: "Claims met the configured accept policy.", RERANK: "A stronger candidate was selected by the existing ranking policy.",
    CORRECT: "Visual evidence supported an evidence-backed correction.", ABSTAIN: "Evidence did not justify a confident accept or correction.",
  };
  return <div className="flex gap-3 rounded-2xl border border-white/[.08] bg-white/[.025] p-4"><span className="grid size-9 shrink-0 place-items-center rounded-xl border border-white/[.07] bg-white/[.035]"><Icon size={16} className={candidate.decision === "ACCEPT" || candidate.decision === "RERANK" ? "text-emerald-200" : candidate.decision === "ABSTAIN" ? "text-amber-100" : "text-rose-200"}/></span><div><div className="flex items-center gap-2"><Eyebrow>Decision</Eyebrow><Pill tone={statusTone(candidate.decision)}>{candidate.decision}</Pill></div><p className="mt-2 text-xs leading-5 text-zinc-500">{copy[candidate.decision] ?? "Decision returned by the existing verifier."}</p></div></div>;
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
    <TransformWrapper minScale={.6} maxScale={4} initialScale={1} centerOnInit limitToBounds={false}><div className="relative"><TransformComponent wrapperClass="!h-auto !w-full" contentClass="relative !h-auto !w-full">
      <div className="relative w-full"><img src={imageUrl} onLoad={(event) => setNaturalSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} alt="Uploaded image under visual verification" className="block h-auto w-full"/>
        <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 ${naturalSize.width || candidate.evidence.reduce((max, item) => Math.max(max, ...item.boxes.map((box) => box[2] ?? 0)), 0) || 1} ${naturalSize.height || candidate.evidence.reduce((max, item) => Math.max(max, ...item.boxes.map((box) => box[3] ?? 0)), 0) || 1}`} preserveAspectRatio="none" aria-hidden="true">
          {evidence.flatMap((item) => item.boxes.map((box, index) => {
            const active = item.claim_id === selectedClaimId;
            const color = item.status === "SUPPORTED" ? "#79d6a1" : item.status === "AMBIGUOUS" ? "#e6bd75" : "#f27c84";
            return <g key={`${item.claim_id}-${index}`} opacity={selectedClaimId && !active ? .18 : .95}><rect x={box[0]} y={box[1]} width={box[2] - box[0]} height={box[3] - box[1]} fill="none" stroke={color} strokeWidth={active ? 4 : 2}/>{active && <text x={box[0] + 4} y={Math.max(13, box[1] - 6)} fill={color} fontSize="13" fontFamily="monospace">{item.claim_id} · {item.status} · {percent(item.confidence)}</text>}</g>;
          }))}
        </svg>
      </div>
    </TransformComponent></div><div className="absolute bottom-3 right-3 z-10 rounded-lg border border-white/10 bg-black/65 px-2 py-1 mono text-[8px] text-zinc-500">Scroll / pinch to zoom · drag to pan</div></TransformWrapper>
    <div className="flex flex-wrap items-center gap-3 border-t border-white/[.06] px-3 py-2.5">{[["#79d6a1", "Supported"], ["#e6bd75", "Ambiguous"], ["#f27c84", "Contradicted / unsupported"]].map(([color, label]) => <span key={label} className="flex items-center gap-1.5 text-[9px] text-zinc-600"><i className="size-1.5 rounded-sm" style={{ backgroundColor: color }}/>{label}</span>)}</div>
  </div>;
}

function ClaimList({ candidate, compact = false }: { candidate: Candidate; compact?: boolean }) {
  const selectedClaimId = useWorkspace((state) => state.selectedClaimId);
  const selectClaim = useWorkspace((state) => state.selectClaim);
  const records = candidate.claims.map((claim) => ({ claim, evidence: candidate.evidence.find((item) => item.claim_id === claim.id) }));
  if (!records.length) return <EmptyState icon={<ScanEye size={18}/>} title="No claims extracted" detail="The response did not produce typed claims for inspection."/>;
  return <div className="space-y-2">{records.map(({ claim, evidence }) => <button key={claim.id} onClick={() => selectClaim(selectedClaimId === claim.id ? null : claim.id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedClaimId === claim.id ? "border-violet-200/30 bg-violet-200/[.055]" : "border-white/[.06] bg-white/[.012] hover:border-white/[.12] hover:bg-white/[.025]"}`} aria-pressed={selectedClaimId === claim.id}>
    <div className="flex items-start justify-between gap-2"><div><span className="mono mr-2 text-[9px] text-violet-200/80">{claim.id}</span><span className="text-xs font-medium text-zinc-200">{claim.subject}</span></div><Pill tone={statusTone(evidence?.status)}>{evidence?.status ?? "NO EVIDENCE"}</Pill></div>
    <div className="mt-1.5 pl-[34px] text-[11px] text-zinc-500">{claim.attribute ? `${claim.attribute} · ` : ""}{claim.value ?? claim.type}{claim.object ? ` → ${claim.object}` : ""}</div>
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
    resolver: zodResolver(formSchema), defaultValues: { query: "Describe the objects and their colors.", provider: "", candidateCount: 3, manualResponse: "", verificationWeight: .75, agreementWeight: .25, highThreshold: .8, lowThreshold: .4 },
  });
  useEffect(() => {
    if (!configQuery.data) return;
    reset({ query: "Describe the objects and their colors.", provider: configQuery.data.provider, candidateCount: configQuery.data.defaults.candidate_count, manualResponse: "", verificationWeight: configQuery.data.defaults.verification_weight, agreementWeight: configQuery.data.defaults.agreement_weight, highThreshold: configQuery.data.defaults.high_threshold, lowThreshold: configQuery.data.defaults.low_threshold });
  }, [configQuery.data, reset]);
  const mutation = useMutation({ mutationFn: async (values: AnalysisForm) => {
    if (!file) throw new Error("Choose an image to analyze.");
    return analyzeImage({ file, query: values.query, provider: values.provider, candidateCount: values.candidateCount, manualResponse: values.manualResponse, verificationWeight: values.verificationWeight, agreementWeight: values.agreementWeight, highThreshold: values.highThreshold, lowThreshold: values.lowThreshold });
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
            {zoomImage && <span className="absolute bottom-2 left-2 rounded-md bg-black/70 px-2 py-1 mono text-[8px] text-zinc-300">{file?.name ?? "Uploaded image"}</span>}
          </label>
        </Panel>
        <Panel className="p-4 sm:p-5"><div className="mb-4 flex items-center justify-between"><Eyebrow>02 / Analysis controls</Eyebrow><SlidersHorizontal size={14} className="text-zinc-600"/></div>
          <label className="mb-1.5 block text-[10px] text-zinc-500" htmlFor="query">Question</label><textarea id="query" {...register("query")} rows={2} className="w-full resize-y rounded-xl border border-white/[.09] bg-black/20 px-3 py-2.5 text-xs leading-5 text-zinc-200 placeholder:text-zinc-700 focus:border-violet-200/30 focus:outline-none"/>{errors.query && <p className="mt-1 text-[10px] text-rose-300">{errors.query.message}</p>}
          <div className="mt-4 grid grid-cols-2 gap-3"><label className="text-[10px] text-zinc-500">Generator model<select {...register("provider")} className="mt-1.5 w-full rounded-lg border border-white/[.09] bg-[#111318] px-2.5 py-2 text-xs text-zinc-200" disabled={configQuery.isPending}>{(configQuery.data?.models ?? []).map((item) => <option key={item.id} value={item.id}>{item.model}</option>)}</select></label><label className="text-[10px] text-zinc-500">Candidates<select {...register("candidateCount", { valueAsNumber: true })} className="mt-1.5 w-full rounded-lg border border-white/[.09] bg-[#111318] px-2.5 py-2 text-xs text-zinc-200">{[1,2,3].map((n) => <option key={n} value={n}>{n}</option>)}</select></label></div><p className="mt-3 text-[9px] leading-4 text-zinc-600">Visual verifier: Grounding DINO object grounding + CLIP attribute checks on grounded crops. No verifier LLM is called.</p>
          <details className="group mt-4 border-t border-white/[.06] pt-3"><summary className="flex cursor-pointer list-none items-center justify-between text-[10px] text-zinc-600">Reliability policy <ChevronDown size={13} className="transition group-open:rotate-180"/></summary><div className="mt-4 grid grid-cols-2 gap-x-3 gap-y-4">{([["verificationWeight","Visual weight"],["agreementWeight","Agreement"],["highThreshold","Accept at"],["lowThreshold","Correct below"]] as const).map(([key,label]) => <label key={key} className="text-[9px] text-zinc-600">{label}<span className="mono float-right text-zinc-400">{Number(watch(key)).toFixed(2)}</span><input type="range" min="0" max="1" step=".05" {...register(key,{valueAsNumber:true})} className="mt-2 w-full accent-violet-300"/></label>)}</div><p className="mt-3 text-[9px] leading-4 text-zinc-700">Model token probabilities are not available from this provider call; the existing scorer handles that policy.</p></details>
          <details className="mt-3 border-t border-white/[.06] pt-3"><summary className="cursor-pointer text-[10px] text-zinc-600">Controlled candidate override</summary><textarea {...register("manualResponse")} rows={3} placeholder="Optional. Separate multiple candidate texts with |||" className="mt-3 w-full rounded-lg border border-white/[.09] bg-black/20 px-3 py-2 text-[10px] leading-5 text-zinc-300 placeholder:text-zinc-700 focus:outline-none"/></details>
          <Button type="submit" className="mt-5 h-11 w-full" disabled={!file || mutation.isPending}>{mutation.isPending ? <><LoaderCircle size={15} className="animate-spin"/> Running verifier…</> : <>Run reliability analysis <ArrowRight size={14}/></>}</Button>
          {mutation.isPending && <p className="mt-3 flex items-center gap-2 text-[10px] text-zinc-600"><span className="size-1.5 animate-pulse rounded-full bg-violet-300"/>Waiting for the existing pipeline to complete. Backend stage-level progress is not exposed.</p>}
        </Panel>
      </div>

      <div className="space-y-4">
        <Panel className="p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><Eyebrow>03 / Visual evidence</Eyebrow>{best && <Pill tone="violet">{best.evidence.length} evidence records</Pill>}</div>{best ? <ImageViewer candidate={best}/> : <EmptyState icon={<ScanEye size={18}/>} title="Evidence canvas" detail="Run an analysis to see verified boxes and claim-linked highlighting."/>}</Panel>
        <Panel className="p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><Eyebrow>04 / Claim inspector</Eyebrow>{best && <span className="mono text-[9px] text-zinc-600">{best.claims.length} CLAIMS</span>}</div>{best ? <ClaimList candidate={best}/> : <EmptyState icon={<Activity size={18}/>} title="Claims will appear here" detail="Typed claims are extracted from the model response after analysis."/>}</Panel>
      </div>

      <div className="space-y-4">
        {best ? <>
          {analysis!.candidates.length > 1 && <Panel className="p-4"><div className="mb-3 flex items-center justify-between"><Eyebrow>Candidate selection</Eyebrow><span className="mono text-[9px] text-zinc-600">{analysis!.candidates.length} TOTAL</span></div><select value={activeCandidate} onChange={(event) => setCandidate(Number(event.target.value))} className="w-full rounded-lg border border-white/[.09] bg-[#111318] px-3 py-2 text-xs text-zinc-200">{analysis!.candidates.map((candidate,index) => <option key={candidate.id} value={index}>{index + 1} · {candidate.id} · {candidate.decision} · {percent(candidate.reliability)}</option>)}</select></Panel>}
          <ReliabilityPanel candidate={best}/><DecisionPanel candidate={best}/>
          <Panel className="p-4 sm:p-5"><div className="flex items-center justify-between"><Eyebrow>Original model response</Eyebrow><Pill>{best.model}</Pill></div><p className="mt-4 text-sm leading-7 text-zinc-300">{best.original_response ?? best.text}</p><p className="mt-3 mono text-[9px] text-zinc-700">{analysis!.experiment_id ? `RUN ${String(analysis!.experiment_id).padStart(4, "0")} · ` : ""}Generator model: {best.model || "unavailable"} · visual verification: Grounding DINO + CLIP region probe{best.latency_ms != null ? ` · ${(best.latency_ms / 1000).toFixed(1)}s` : ""} · {best.id} · agreement {percent(best.agreement)}</p></Panel>
          <Panel className="p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><Eyebrow>Correction</Eyebrow><Sparkles size={13} className="text-violet-200/50"/></div>{best.corrected_text && best.corrected_text !== best.text ? <><div className="text-xs leading-6 text-zinc-600">Original: <span className="text-zinc-400">{best.text}</span></div><div className="mt-3 border-t border-white/[.06] pt-3 text-xs leading-6 text-emerald-100/90">{best.corrected_text}</div><p className="mt-2 text-[10px] text-zinc-600">Only supported changes from the backend correction engine.</p></> : <p className="text-xs leading-5 text-zinc-600">No evidence-backed correction was returned. Uncertain claims are retained.</p>}</Panel>
        </> : <Panel className="p-5"><EmptyState icon={<ShieldCheck size={18}/>} title="Awaiting verification" detail="Reliability and decision panels will show values returned by the backend, never simulated scores."/></Panel>}
      </div>
    </form>
    {best && <Panel className="mt-4 overflow-hidden p-4 sm:p-5"><div className="mb-3 flex items-center justify-between"><div><Eyebrow>Claim graph</Eyebrow><p className="mt-1 text-[10px] text-zinc-600">Select a node to focus the matching claim and its image evidence.</p></div><Pill tone="violet">backend graph data</Pill></div><ClaimGraph graph={best.graph} selectedCandidate={best}/></Panel>}
  </>;
}

function ClaimsPage() {
  const analysis = useWorkspace((state) => state.analysis); const index = useWorkspace((state) => state.activeCandidate); const candidate = analysis?.candidates[index] ?? analysis?.candidates[0];
  return <><PageHeading eyebrow="Claim graph / typed extraction" title="A response, decomposed." detail="Select a claim to highlight it in the graph and inspect its corresponding evidence."/>{candidate ? <div className="grid gap-4 xl:grid-cols-[.75fr_1.25fr]"><Panel className="p-4 sm:p-5"><Eyebrow>Extracted claims</Eyebrow><div className="mt-4"><ClaimList candidate={candidate}/></div></Panel><Panel className="p-4 sm:p-5"><Eyebrow>Claim graph</Eyebrow><div className="mt-3"><ClaimGraph graph={candidate.graph} selectedCandidate={candidate}/></div></Panel></div> : <EmptyState icon={<Activity size={18}/>} title="No analysis to inspect" detail="Run an image analysis first. Claim IDs, graph edges, and statuses come from real backend output." action={<Link href="/analyze"><Button>Go to Analyze <ArrowRight size={14}/></Button></Link>}/>}</>;
}

function EvidencePage() {
  const analysis = useWorkspace((state) => state.analysis);
  const index = useWorkspace((state) => state.activeCandidate);
  const candidate = analysis?.candidates[index] ?? analysis?.candidates[0];
  const selectClaim = useWorkspace((state) => state.selectClaim);
  return <>
    <PageHeading eyebrow="Visual verification / evidence" title="Trace the visual support." detail="Every status and score below is returned by the verification backend; missing evidence stays explicitly unavailable." />
    {candidate ? <div className="grid gap-4 xl:grid-cols-[1.1fr_.9fr]">
      <Panel className="p-4"><ImageViewer candidate={candidate}/></Panel>
      <div className="space-y-2">{candidate.evidence.map((item: Evidence) => <button key={item.claim_id} onClick={() => selectClaim(item.claim_id)} className="surface block w-full rounded-2xl p-4 text-left transition hover:border-white/[.16]">
        <div className="flex items-center justify-between"><div><Eyebrow>{item.claim_id} / {item.diagnosis ?? "VERIFICATION"}</Eyebrow><p className="mt-2 text-xs text-zinc-300">{candidate.claims.find((claim) => claim.id === item.claim_id)?.text || candidate.claims.find((claim) => claim.id === item.claim_id)?.subject || "Claim details unavailable"}</p></div><Pill tone={statusTone(item.status)}>{item.status}</Pill></div>
        <p className="mt-3 text-[11px] leading-5 text-zinc-500">{item.explanation || "Visual evidence explanation unavailable."}</p>
        <div className="mt-3 flex flex-wrap gap-2">{item.source?.length ? item.source.map((source) => <Pill key={source}>{source}</Pill>) : <Pill>Sources unavailable</Pill>}<Pill tone="violet">Score {percent(item.score)}</Pill>{item.confidence > 0 && <Pill>Verifier estimate · uncalibrated {percent(item.confidence)}</Pill>}</div>
        {item.signals && Object.keys(item.signals).length > 0 && <details onClick={(event) => event.stopPropagation()} className="mt-3 border-t border-white/[.06] pt-3"><summary className="cursor-pointer text-[10px] text-zinc-600">Inspect returned signals</summary><pre className="mt-2 overflow-auto text-[9px] leading-4 text-zinc-500">{JSON.stringify(item.signals, null, 2)}</pre></details>}
      </button>)}</div>
    </div> : <EmptyState icon={<ScanEye size={18}/>} title="Visual evidence unavailable" detail="Run an analysis to inspect claim-linked boxes, verifier sources, and contradiction signals." action={<Link href="/analyze"><Button>Start an analysis</Button></Link>} />}
  </>;
}

function CandidatesPage() {
  const analysis = useWorkspace((state) => state.analysis); const setCandidate = useWorkspace((state) => state.setCandidate);
  const candidates = analysis?.candidates ?? [];
  const chart = candidates.map((item, index) => ({ name: `Candidate ${String(index + 1).padStart(2,"0")}`, reliability: Math.round(item.reliability * 100), agreement: Math.round(item.agreement * 100) }));
  return <><PageHeading eyebrow="Candidate comparison / actual run" title="Compare what the model said." detail="Candidates are ordered and scored by the existing verifier. Every chart point corresponds to a real returned candidate."/>{candidates.length ? <><Panel className="p-5"><Eyebrow>Measured comparison · percent</Eyebrow><CandidateChart data={chart}/></Panel><div className="mt-4 grid gap-3 lg:grid-cols-2">{candidates.map((candidate,index) => <button key={candidate.id} onClick={() => setCandidate(index)} className={`surface rounded-2xl p-5 text-left transition ${index === 0 ? "border-violet-200/20" : "hover:border-white/15"}`}><div className="flex items-start justify-between"><div><Eyebrow>Candidate {String(index+1).padStart(2,"0")}</Eyebrow><h3 className="mt-2 text-2xl font-medium tracking-[-.05em]">{percent(candidate.reliability)}</h3></div><Pill tone={statusTone(candidate.decision)}>{candidate.decision}</Pill></div><p className="mt-3 line-clamp-3 text-xs leading-6 text-zinc-400">{candidate.text}</p><div className="mt-4 flex flex-wrap gap-2"><Pill>{candidate.claims.length} claims</Pill><Pill>{candidate.evidence.length} evidence records</Pill><Pill>agreement {percent(candidate.agreement)}</Pill></div><div className="mt-4 border-t border-white/[.06] pt-3 text-[10px] text-zinc-600">{candidate.diagnosis.length ? candidate.diagnosis.join(" · ") : "No diagnosis returned"}</div></button>)}</div></> : <EmptyState icon={<Layers3 size={18}/>} title="No candidates to compare" detail="Run an analysis with multiple candidates or provide candidate overrides separated by |||." action={<Link href="/analyze"><Button>Run analysis</Button></Link>}/>}</>;
}

function EvaluationPage() {
  const query = useQuery({ queryKey: ["evaluation"], queryFn: getEvaluation });
  return <><PageHeading eyebrow="Evaluation / labelled results only" title="Measure what the evidence can support." detail="A research view for benchmark and labelled experiment data. No synthetic metrics or baseline scores are shown."/>{query.data?.available ? <Panel className="p-6"><Eyebrow>Labelled evaluation available</Eyebrow><pre className="mt-4 overflow-auto text-xs text-zinc-400">{JSON.stringify(query.data,null,2)}</pre></Panel> : <EmptyState icon={<Database size={18}/>} title="No labelled evaluation set connected" detail={query.data?.message ?? "Precision, recall, F1, Brier score, calibration, and correction success will appear when labelled evaluation records are supplied. The existing evaluator currently has no records."}/>}{query.isError && <p role="alert" className="mt-3 text-xs text-rose-300">Could not reach the evaluation service: {(query.error as Error).message}</p>}</>;
}

function ExperimentsPage() {
  const list = useQuery({ queryKey: ["history"], queryFn: getHistory });
  const [active, setActive] = useState<number | null>(null);
  const item = useQuery({ queryKey: ["history", active], queryFn: () => getHistoryItem(active!), enabled: active !== null });
  const open = (row: HistorySummary) => setActive(row.id);
  return <><PageHeading eyebrow="Local run history / SQLite" title="Every run, traceable." detail="Experiment records are loaded from the existing database and opened without changing its schema."/>{list.isPending ? <Panel className="animate-pulse p-7"><div className="h-4 w-48 rounded bg-white/[.05]"/><div className="mt-5 h-24 rounded-xl bg-white/[.03]"/></Panel> : list.isError ? <EmptyState icon={<Database size={18}/>} title="History service unavailable" detail={(list.error as Error).message}/> : !list.data?.length ? <EmptyState icon={<Clock3 size={18}/>} title="No experiments yet" detail="Completed analyses will be stored in the existing SQLite history."/> : <div className="grid gap-4 xl:grid-cols-[.8fr_1.2fr]"><Panel className="overflow-hidden"><div className="border-b border-white/[.06] px-4 py-3"><Eyebrow>Recent experiments</Eyebrow></div><div className="max-h-[640px] overflow-auto">{list.data.map((row) => <button key={row.id} onClick={() => open(row)} className={`block w-full border-b border-white/[.05] px-4 py-4 text-left transition hover:bg-white/[.025] ${active === row.id ? "bg-violet-200/[.045]" : ""}`}><div className="flex items-center justify-between"><span className="mono text-[9px] text-zinc-600">RUN {String(row.id).padStart(4,"0")}</span><span className="mono text-[9px] text-zinc-700">{row.created_at}</span></div><p className="mt-2 line-clamp-2 text-xs leading-5 text-zinc-300">{row.query}</p></button>)}</div></Panel><Panel className="min-h-72 p-5">{item.isPending ? <div className="animate-pulse text-xs text-zinc-600">Loading experiment…</div> : item.data ? <><div className="flex items-center justify-between"><Eyebrow>Run {String(item.data.id).padStart(4,"0")} · {item.data.created_at}</Eyebrow><a href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(item.data.payload,null,2))}`} download={`experiment-${item.data.id}.json`} className="inline-flex items-center gap-1.5 text-[10px] text-zinc-500 hover:text-zinc-200"><Download size={13}/> Export JSON</a></div><h2 className="mt-3 text-lg font-medium tracking-[-.04em]">{item.data.query}</h2><div className="mt-5 space-y-3">{item.data.payload.candidates.map((candidate) => <div key={candidate.id} className="rounded-xl border border-white/[.07] bg-white/[.015] p-4"><div className="flex items-center justify-between"><span className="mono text-[9px] text-zinc-600">{candidate.id} · {candidate.model}</span><Pill tone={statusTone(candidate.decision)}>{candidate.decision} · {percent(candidate.reliability)}</Pill></div><p className="mt-3 text-xs leading-6 text-zinc-300">{candidate.text}</p><p className="mt-2 text-[10px] text-zinc-600">{candidate.claims.length} claims · {candidate.evidence.length} evidence records · image not persisted</p></div>)}</div></> : <EmptyState icon={<Clock3 size={18}/>} title="Select an experiment" detail="Open a run to inspect its response, claims, and saved evidence."/>}</Panel></div>}</>;
}

export function WorkspaceShell({ section }: { section: string }) {
  const [eyebrow,title,detail] = titles[section];
  const pages: Record<string, () => React.ReactNode> = { analyze: AnalysisWorkspace, claims: ClaimsPage, evidence: EvidencePage, candidates: CandidatesPage, evaluation: EvaluationPage, experiments: ExperimentsPage };
  const Page = pages[section];
  return <main className="min-h-screen bg-[#0b0c0f]"><SiteHeader/><div className="mx-auto max-w-[1480px] px-4 pb-20 pt-28 sm:px-7 lg:px-10"><div className="mb-6 flex gap-1 overflow-x-auto border-b border-white/[.06] pb-3 hide-scrollbar">{Object.entries(titles).map(([key,[label]]) => <Link key={key} href={`/${key}`} className={`whitespace-nowrap rounded-lg px-3 py-2 text-[10px] transition ${section === key ? "bg-white/[.07] text-zinc-100" : "text-zinc-600 hover:text-zinc-300"}`}>{label.split(" / ")[1]}</Link>)}</div><Page/></div><footer className="border-t border-white/[.05] px-4 py-5 text-center"><span className="mono text-[8px] uppercase tracking-[.15em] text-zinc-800">Local-first · evidence-linked · uncertainty-aware</span></footer></main>;
}
