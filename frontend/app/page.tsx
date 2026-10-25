"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowRight, ArrowUpRight, Check, CircleDot, Eye, Fingerprint, GitBranch, Layers3, ShieldCheck, Sparkles, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SiteHeader } from "@/components/site-header";
import { Button, Eyebrow, Panel, Pill } from "@/components/ui";

const steps = [
  { icon: Layers3, label: "VLM RESPONSE", copy: "A fluent answer is only a starting point." },
  { icon: GitBranch, label: "CLAIMS", copy: "Break the sentence into things that can be checked." },
  { icon: Eye, label: "VISUAL EVIDENCE", copy: "Ground each claim in detected image evidence." },
  { icon: ShieldCheck, label: "RELIABILITY", copy: "Measure support, contradiction, and uncertainty." },
  { icon: Check, label: "CORRECTION", copy: "Change only what the evidence justifies." },
];

const demoFrames = [
  { label: "VLM RESPONSE", color: "text-zinc-100", line: "“A blue car and red bicycle.”", detail: "A plausible answer can still bind the right attributes to the wrong objects." },
  { label: "CLAIMS EXTRACTED", color: "text-violet-200", line: "CAR → BLUE     BICYCLE → RED", detail: "The response becomes typed, inspectable claims." },
  { label: "VISUAL EVIDENCE", color: "text-cyan-200", line: "CAR → RED       BICYCLE → BLUE", detail: "Evidence is evaluated against the image, object by object." },
  { label: "ATTRIBUTE BINDING ERROR", color: "text-amber-200", line: "Claimed attributes conflict with the crops.", detail: "A contradiction is not hidden by a fluent sentence." },
  { label: "CORRECTED · ILLUSTRATIVE", color: "text-emerald-200", line: "“A red car and blue bicycle.”", detail: "Illustrative walkthrough only — not a live model result or benchmark." },
];

function Demo() {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const reduce = useReducedMotion();
  useEffect(() => {
    if (!playing || reduce) return;
    const timer = window.setInterval(() => setIndex((value) => (value + 1) % demoFrames.length), 2600);
    return () => window.clearInterval(timer);
  }, [playing, reduce]);
  const frame = demoFrames[index];
  return <Panel className="relative overflow-hidden p-5 sm:p-7">
    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_88%_0%,rgba(126,98,184,.13),transparent_50%)]"/>
    <div className="relative">
      <div className="flex items-center justify-between"><Eyebrow>Illustrative walkthrough</Eyebrow><button onClick={() => setPlaying(!playing)} className="mono text-[9px] uppercase tracking-widest text-zinc-600 hover:text-zinc-300" aria-pressed={playing}>{playing ? "Pause" : "Play"}</button></div>
      <div className="mt-6 grid gap-4 sm:grid-cols-[.82fr_1.18fr]">
        <div className="relative flex min-h-48 items-center justify-center overflow-hidden rounded-xl border border-white/[.07] bg-[#0b0c10]">
          <div className="absolute inset-0 soft-grid opacity-70"/>
          <div className="relative flex items-end gap-4 pb-7">
            <div className="relative"><div className="h-9 w-24 rounded-[25px_30px_8px_8px] border border-rose-200/25 bg-rose-400/20"/><div className="absolute -top-3 left-5 h-4 w-12 rounded-t-full border border-rose-200/20 bg-rose-300/15"/><div className="absolute -bottom-2 left-3 size-6 rounded-full border-4 border-[#24262c] bg-[#101116]"/><div className="absolute -bottom-2 right-3 size-6 rounded-full border-4 border-[#24262c] bg-[#101116]"/><span className="absolute -top-8 left-2 mono text-[8px] text-rose-200/70">CAR · RED</span></div>
            <div className="relative mb-1"><div className="size-12 rounded-full border border-cyan-200/25"/><div className="absolute left-0 top-5 h-px w-14 rotate-[-28deg] bg-cyan-100/45"/><div className="absolute left-5 top-[-2px] h-9 w-px rotate-[32deg] bg-cyan-100/45"/><div className="absolute -bottom-1 -left-1 size-4 rounded-full border-2 border-[#262832] bg-[#111318]"/><div className="absolute -bottom-1 right-[-3px] size-4 rounded-full border-2 border-[#262832] bg-[#111318]"/><span className="absolute -top-8 -left-2 whitespace-nowrap mono text-[8px] text-cyan-100/70">BICYCLE · BLUE</span></div>
          </div>
          <span className="absolute bottom-3 left-3 mono text-[8px] uppercase tracking-widest text-zinc-700">Concept scene · not analyzed data</span>
        </div>
        <div className="flex min-h-48 flex-col justify-between rounded-xl border border-white/[.07] bg-white/[.018] p-4 sm:p-5">
          <div className="flex items-center justify-between"><span className="mono text-[9px] tracking-[.14em] text-zinc-600">01 — 05</span><span className="flex gap-1" aria-label={`Step ${index + 1} of ${demoFrames.length}`}>{demoFrames.map((item, i) => <button key={item.label} onClick={() => { setIndex(i); setPlaying(false); }} aria-label={`Show ${item.label}`} className={`h-1 rounded-full transition-all ${i === index ? "w-6 bg-violet-300" : "w-2 bg-white/15"}`}/>)}</span></div>
          <AnimatePresence mode="wait"><motion.div key={frame.label} initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={reduce ? undefined : { opacity: 0, y: -6 }} transition={{ duration: .32 }} className="py-5"><Eyebrow>{frame.label}</Eyebrow><div className={`mt-3 text-[15px] font-semibold leading-7 tracking-[-.025em] ${frame.color}`}>{frame.line}</div><p className="mt-2 text-xs leading-5 text-zinc-500">{frame.detail}</p></motion.div></AnimatePresence>
          <div className="flex items-center gap-2 border-t border-white/[.06] pt-3"><CircleDot size={12} className="text-violet-300"/><span className="text-[10px] text-zinc-600">Evidence before confidence.</span></div>
        </div>
      </div>
    </div>
  </Panel>;
}

export default function HomePage() {
  const storyRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    gsap.registerPlugin(ScrollTrigger);
    const context = gsap.context(() => {
      gsap.utils.toArray<HTMLElement>("[data-story]").forEach((node) => {
        gsap.fromTo(node, { opacity: .24, y: 32 }, { opacity: 1, y: 0, duration: .7, ease: "power2.out", scrollTrigger: { trigger: node, start: "top 82%", end: "top 50%", scrub: .7 } });
      });
      gsap.to(".hero-orb", { yPercent: 24, ease: "none", scrollTrigger: { trigger: ".hero-section", start: "top top", end: "bottom top", scrub: true } });
    }, storyRef);
    return () => context.revert();
  }, []);
  return <main ref={storyRef} className="overflow-hidden">
    <SiteHeader/>
    <section className="hero-section grain relative min-h-[790px] overflow-hidden border-b border-white/[.055] pt-28 sm:pt-32">
      <div className="soft-grid absolute inset-x-0 top-0 h-[680px] opacity-80"/><div className="hero-orb absolute -right-32 top-6 size-[540px] rounded-full bg-[radial-gradient(circle,rgba(126,99,196,.17),transparent_68%)] blur-2xl"/>
      <div className="relative z-10 mx-auto grid max-w-[1480px] items-center gap-12 px-4 pb-16 pt-10 sm:px-7 lg:grid-cols-[.92fr_1.08fr] lg:px-10 lg:pb-24 lg:pt-12">
        <div><div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/[.09] bg-white/[.025] px-3 py-1.5"><span className="size-1.5 rounded-full bg-violet-300 shadow-[0_0_12px_#ab92fa]"/><Eyebrow>VLM Reliability Layer</Eyebrow></div>
          <h1 className="max-w-[750px] text-balance text-[clamp(3.6rem,7.2vw,6.6rem)] font-semibold leading-[.97] tracking-[-.078em] text-zinc-100">AI shouldn’t be the <span className="bg-gradient-to-r from-zinc-100 via-violet-100 to-zinc-400 bg-clip-text text-transparent">only one</span> checking AI.</h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-zinc-500 sm:text-lg">AI generates the answer. We verify whether the image actually supports it.</p>
          <div className="mt-8 flex flex-wrap gap-3"><Link href="/analyze"><Button className="h-12 px-5">Analyze an image <ArrowRight size={15}/></Button></Link><a href="#system"><Button variant="secondary" className="h-12 px-5">Explore the system <ArrowDown size={14}/></Button></a></div>
          <div className="mt-10 flex items-center gap-3 text-[11px] text-zinc-600"><Fingerprint size={15} className="text-violet-300/70"/><span>Claim-level verification · evidence-linked decisions · explicit uncertainty</span></div>
        </div>
        <div className="relative"><div className="absolute -inset-6 rounded-[32px] bg-violet-300/[.025] blur-2xl"/><Demo/></div>
      </div>
      <div className="relative z-10 mx-auto max-w-[1480px] px-4 pb-7 sm:px-7 lg:px-10"><div className="flex items-center justify-between border-t border-white/[.06] pt-5"><span className="mono text-[9px] uppercase tracking-[.16em] text-zinc-700">The verification layer for vision-language systems</span><a href="#system" className="mono flex items-center gap-2 text-[9px] uppercase tracking-[.14em] text-zinc-600 hover:text-zinc-300">Scroll to explore <ArrowDown size={11}/></a></div></div>
    </section>
    <section id="system" className="relative mx-auto max-w-[1480px] px-4 py-24 sm:px-7 lg:px-10 lg:py-32">
      <div className="mb-12 grid gap-5 lg:grid-cols-[.7fr_1.3fr] lg:items-end"><div><Eyebrow>A more careful kind of AI</Eyebrow><h2 className="mt-4 max-w-md text-3xl font-medium leading-tight tracking-[-.055em] text-zinc-100 sm:text-4xl">Seeing is not the same as being right.</h2></div><p className="max-w-xl text-sm leading-7 text-zinc-500 lg:justify-self-end">A VLM response contains claims about objects, attributes, quantities, and relationships. We inspect those claims against visual evidence—then make uncertainty visible.</p></div>
      <div className="grid gap-3 md:grid-cols-5">{steps.map((step, i) => <motion.div data-story key={step.label} whileHover={{ y: -4 }} className="surface relative min-h-44 rounded-2xl p-5"><span className="mono text-[9px] text-zinc-700">0{i + 1}</span><step.icon size={18} className="mt-6 text-violet-200/75"/><h3 className="mt-4 mono text-[9px] tracking-[.11em] text-zinc-300">{step.label}</h3><p className="mt-2 text-xs leading-5 text-zinc-600">{step.copy}</p>{i < steps.length - 1 && <ArrowRight size={13} className="absolute right-3 top-1/2 hidden -translate-y-1/2 text-zinc-700 md:block"/>}</motion.div>)}</div>
    </section>
    <section className="border-y border-white/[.055] bg-[#0e0f13]">
      <div className="mx-auto max-w-[1480px] px-4 py-24 sm:px-7 lg:px-10 lg:py-32"><div className="grid gap-12 lg:grid-cols-[.85fr_1.15fr]">
        <div className="lg:sticky lg:top-32 lg:h-fit"><Eyebrow>The reliability question</Eyebrow><h2 className="mt-4 max-w-lg text-4xl font-medium leading-[1.08] tracking-[-.06em] text-zinc-100 sm:text-5xl">A confident sentence is not evidence.</h2><p className="mt-5 max-w-md text-sm leading-7 text-zinc-500">Reliability starts with an answerable question: which parts of this response are actually supported by the image?</p><Link href="/analyze" className="mt-7 inline-flex items-center gap-2 text-sm text-violet-200 hover:text-white">Inspect a real analysis <ArrowUpRight size={14}/></Link></div>
        <div className="space-y-3">{[
          ["VLMs can see.", "They turn pixels into fluent descriptions."],
          ["But fluency can hide a mismatch.", "The right object can be paired with the wrong color."],
          ["Every answer contains checkable claims.", "Objects, attributes, quantities, and relations."],
          ["Evidence has limits.", "The verifier should abstain when the image is unclear."],
          ["A correction should be earned.", "Change only claims contradicted by sufficient evidence."],
          ["Sometimes the right answer is uncertainty.", "Abstention protects against unsupported certainty."],
        ].map(([title, detail], i) => <div data-story key={title} className="surface rounded-xl p-5 sm:p-6"><div className="flex gap-4"><span className="mono mt-0.5 text-[10px] text-violet-300/70">0{i + 1}</span><div><h3 className="text-base font-medium tracking-[-.025em] text-zinc-200">{title}</h3><p className="mt-1.5 text-sm leading-6 text-zinc-600">{detail}</p></div></div></div>)}</div>
      </div></div>
    </section>
    <section className="mx-auto max-w-[1480px] px-4 py-24 text-center sm:px-7 lg:px-10 lg:py-32"><div data-story className="mx-auto max-w-3xl"><Eyebrow>Evidence before confidence</Eyebrow><h2 className="mt-5 text-balance text-4xl font-medium leading-[1.08] tracking-[-.065em] text-zinc-100 sm:text-6xl">AI that knows when it might be wrong.</h2><p className="mx-auto mt-5 max-w-lg text-sm leading-7 text-zinc-500">Generate. Verify. Understand. Correct—only when the image gives reason.</p><Link href="/analyze" className="mt-8 inline-block"><Button className="h-12 px-6">Analyze an image <ArrowRight size={15}/></Button></Link></div></section>
    <footer className="border-t border-white/[.06] px-4 py-6 text-center"><span className="mono text-[9px] uppercase tracking-[.14em] text-zinc-700">VLM Reliability Layer · AI that doesn’t blindly trust AI</span></footer>
  </main>;
}
