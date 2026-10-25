"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { Activity, ArrowUpRight, Menu, X } from "lucide-react";

const links = [
  ["Analyze", "/analyze"], ["Claims", "/claims"], ["Evidence", "/evidence"],
  ["Candidates", "/candidates"], ["Review", "/review"], ["Evaluation", "/evaluation"], ["Experiments", "/experiments"],
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const update = () => setScrolled(window.scrollY > 18);
    update(); window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);
  return <header className={`glass-nav fixed inset-x-0 top-0 z-50 border-b transition-all duration-300 ${scrolled ? "border-white/[.09]" : "border-white/[.045]"}`}>
    <div className={`mx-auto flex max-w-[1480px] items-center justify-between px-4 transition-all sm:px-7 lg:px-10 ${scrolled ? "h-[58px]" : "h-[68px]"}`}>
      <Link href="/" className="flex items-center gap-2.5" aria-label="VLM Reliability Layer home">
        <span className="grid size-8 place-items-center rounded-[10px] border border-violet-200/20 bg-gradient-to-br from-violet-300/15 to-slate-200/[.02] text-violet-100"><Activity size={16}/></span>
        <span className="text-[13px] font-semibold tracking-[-.035em] text-zinc-100">VLM <span className="text-zinc-500">Reliability Layer</span></span>
      </Link>
      <nav className="hidden items-center gap-1 xl:flex" aria-label="Main navigation">
        {links.map(([label, href]) => <Link key={href} href={href} className={`rounded-lg px-3 py-2 text-[11px] transition-colors ${pathname === href ? "bg-white/[.07] text-zinc-100" : "text-zinc-500 hover:text-zinc-200"}`}>{label}</Link>)}
      </nav>
      <div className="hidden items-center gap-2 xl:flex"><span className="mr-2 mono text-[9px] uppercase tracking-[.14em] text-zinc-600">Research workspace</span><Link href="/analyze" className="group inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[.045] px-3 py-2 text-[11px] font-medium text-zinc-200 transition hover:border-violet-200/20 hover:bg-white/[.08]">Open lab <ArrowUpRight size={13} className="transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"/></Link></div>
      <button className="grid size-10 place-items-center rounded-xl border border-white/10 text-zinc-300 xl:hidden" onClick={() => setOpen(!open)} aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open}>{open ? <X size={17}/> : <Menu size={17}/>}</button>
    </div>
    <AnimatePresence>{open && <motion.nav initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden border-t border-white/[.06] bg-[#0d0e12] xl:hidden" aria-label="Mobile navigation">
      <div className="grid grid-cols-2 gap-1 p-3">{links.map(([label, href]) => <Link onClick={() => setOpen(false)} key={href} href={href} className={`rounded-lg px-3 py-3 text-sm ${pathname === href ? "bg-white/[.07] text-white" : "text-zinc-400"}`}>{label}</Link>)}</div>
    </motion.nav>}</AnimatePresence>
  </header>;
}
