import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

export function Button({ children, variant = "primary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" }) {
  const style = variant === "primary" ? "bg-[#eeeaf8] text-[#18151f] hover:bg-white" : variant === "secondary" ? "border border-white/10 bg-white/[.04] text-white hover:bg-white/[.08]" : "text-zinc-400 hover:bg-white/[.05] hover:text-white";
  return <button className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition duration-200 hover:-translate-y-px active:scale-[.985] disabled:cursor-not-allowed disabled:opacity-50 ${style} ${className}`} {...props}>{children}</button>;
}

export function Panel({ children, className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`surface rounded-2xl ${className}`} {...props}>{children}</div>;
}

export function Eyebrow({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mono text-[10px] uppercase tracking-[.16em] text-violet-300/90 ${className}`}>{children}</div>;
}

export function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warn" | "bad" | "violet" }) {
  const tones = { neutral: "border-white/10 bg-white/[.035] text-zinc-300", good: "border-emerald-300/20 bg-emerald-300/[.07] text-emerald-200", warn: "border-amber-200/20 bg-amber-200/[.07] text-amber-100", bad: "border-rose-300/20 bg-rose-300/[.07] text-rose-200", violet: "border-violet-300/20 bg-violet-300/[.07] text-violet-200" };
  return <span className={`mono inline-flex items-center rounded-full border px-2.5 py-1 text-[9px] uppercase tracking-[.08em] ${tones[tone]}`}>{children}</span>;
}

export function EmptyState({ icon, title, detail, action }: { icon: ReactNode; title: string; detail: string; action?: ReactNode }) {
  return <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[.012] px-6 py-12 text-center"><div className="mb-4 grid size-12 place-items-center rounded-2xl border border-violet-200/10 bg-violet-200/[.05] text-violet-200">{icon}</div><h3 className="text-base font-semibold text-zinc-100">{title}</h3><p className="mt-2 max-w-md text-sm leading-6 text-zinc-500">{detail}</p>{action && <div className="mt-5">{action}</div>}</div>;
}

export function PageHeading({ eyebrow, title, detail, right }: { eyebrow: string; title: string; detail?: string; right?: ReactNode }) {
  return <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><Eyebrow>{eyebrow}</Eyebrow><h1 className="mt-3 text-3xl font-semibold tracking-[-.055em] text-zinc-100 sm:text-4xl">{title}</h1>{detail && <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-500">{detail}</p>}</div>{right}</div>;
}
