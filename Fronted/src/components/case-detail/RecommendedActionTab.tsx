import { useEffect, useMemo, useState } from "react";
import { getManagementSummaries } from "../../services/ai";
import type { CaseAISummary, DocumentItem } from "../../types";
import { cleanAIText } from "../../utils/aiText";

type Props = { caseId: number; documents: DocumentItem[]; onOpenAI: () => void };

function dateLabel(value: string | null) {
  if (!value) return "Keine klare Frist aus dem Dokument erkennbar";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("de-DE");
}

export default function RecommendedActionTab({ caseId, documents, onOpenAI }: Props) {
  const [items, setItems] = useState<CaseAISummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => { void (async () => { try { setLoading(true); setItems(await getManagementSummaries(caseId)); } catch { setError("Die Handlungsempfehlung konnte nicht geladen werden."); } finally { setLoading(false); } })(); }, [caseId]);
  const summary = useMemo(() => items.find((x) => x.status === "Pending") || items.find((x) => ["Approved","EditedAndApproved"].includes(x.status)) || items[0], [items]);
  const docMap = useMemo(() => new Map(documents.map((d) => [d.id, d.file_name])), [documents]);
  if (loading) return <div className="p-8 text-slate-500">Handlungsempfehlung wird geladen...</div>;
  if (error) return <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>;
  if (!summary) return <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center"><h2 className="font-semibold text-slate-900">Noch keine Handlungsempfehlung</h2><p className="mt-2 text-sm text-slate-500">Erstellen Sie zuerst im KI-Assistenten eine Management-Empfehlung aus den bestätigten Dokumenten.</p><button onClick={onOpenAI} className="mt-4 rounded-xl bg-violet-700 px-4 py-2 text-sm font-semibold text-white">KI-Assistent öffnen</button></div>;
  const pending = summary.status === "Pending";
  return <div className="space-y-5">
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-700">Handlungsempfehlung</p><h2 className="mt-2 text-2xl font-semibold text-slate-950">Was muss jetzt konkret getan werden?</h2></div><span className={`rounded-full px-3 py-1 text-xs font-semibold ${pending ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"}`}>{pending ? "KI-Vorschlag · Prüfung ausstehend" : "Vom Benutzer bestätigt"}</span></div>
      <div className="mt-6 rounded-2xl border border-violet-200 bg-violet-50 p-5"><p className="text-xs font-semibold uppercase tracking-wider text-violet-700">Konkrete nächste Maßnahme</p><p className="mt-2 text-lg font-semibold text-violet-950">{cleanAIText(summary.next_required_action) || "Keine konkrete Handlung sicher aus der Evidenz ableitbar."}</p></div>
      <div className="mt-5 grid gap-4 md:grid-cols-2"><div className="rounded-xl border border-slate-200 p-4"><p className="text-xs font-semibold uppercase text-slate-400">Verantwortlich</p><p className="mt-2 font-semibold text-slate-900">{cleanAIText(summary.responsible_role) || "Nicht eindeutig ableitbar"}</p></div><div className="rounded-xl border border-slate-200 p-4"><p className="text-xs font-semibold uppercase text-slate-400">Frist</p><p className="mt-2 font-semibold text-slate-900">{dateLabel(summary.open_deadline)}</p>{summary.deadline_comment && <p className="mt-2 text-sm text-slate-500">{cleanAIText(summary.deadline_comment)}</p>}</div></div>
    </section>
    <section className="grid gap-5 lg:grid-cols-2"><div className="rounded-2xl border border-slate-200 bg-white p-5"><h3 className="font-semibold text-slate-950">1. Fakten aus den Dokumenten</h3>{summary.document_facts?.length ? <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-700">{summary.document_facts.map((f,i)=><li key={i}>{cleanAIText(f)}</li>)}</ul> : <p className="mt-3 text-sm text-slate-500">Keine belastbaren Dokumentfakten strukturiert hinterlegt.</p>}</div><div className="rounded-2xl border border-slate-200 bg-white p-5"><h3 className="font-semibold text-slate-950">2. Einordnung</h3><p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">{cleanAIText(summary.interpretation) || "Keine zusätzliche Interpretation erforderlich oder sicher ableitbar."}</p></div><div className="rounded-2xl border border-slate-200 bg-white p-5"><h3 className="font-semibold text-slate-950">3. Begründung aus der Evidenz</h3><p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">{cleanAIText(summary.action_justification) || "Keine gesonderte Begründung hinterlegt."}</p></div><div className="rounded-2xl border border-amber-200 bg-amber-50 p-5"><h3 className="font-semibold text-amber-950">4. Unsicherheit / noch zu prüfen</h3>{summary.uncertainty_notes?.length ? <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-amber-900">{summary.uncertainty_notes.map((f,i)=><li key={i}>{cleanAIText(f)}</li>)}</ul> : <p className="mt-3 text-sm text-amber-800">Keine zusätzlichen offenen Punkte erkannt.</p>}</div></section>
    <section className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold text-slate-950">Dokumentgrundlage</h3><p className="mt-1 text-sm text-slate-500">Nur bestätigte Evidenz soll die Empfehlung tragen.</p></div>{pending && <button onClick={onOpenAI} className="rounded-xl bg-violet-700 px-4 py-2 text-sm font-semibold text-white">Vorschlag prüfen / bestätigen</button>}</div><div className="mt-3 flex flex-wrap gap-2">{summary.relevant_document_ids?.length ? summary.relevant_document_ids.map((id)=><span key={id} className="rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-700">{docMap.get(id) || `Dokument ${id}`}</span>) : <span className="text-sm text-slate-500">Keine Dokumentreferenz hinterlegt.</span>}</div></section>
  </div>;
}
