import { notFound } from "next/navigation";
import { WorkspaceShell } from "@/components/workspace-shell";

const sections = ["analyze", "claims", "evidence", "candidates", "review", "evaluation", "experiments"];

export default async function WorkspacePage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (!sections.includes(section)) notFound();
  return <WorkspaceShell section={section}/>;
}
