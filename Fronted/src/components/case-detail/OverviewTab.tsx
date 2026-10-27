import { useEffect, useState } from "react";

import { api } from "../../api";
import type { AISuggestion, CaseAISummary, CaseItem, DocumentItem, TaskItem, TimelineEvent } from "../../types";
import { getCaseAISuggestions, getLatestApprovedManagementSummary } from "../../services/ai";
import { cleanAIText } from "../../utils/aiText";
import { RiskBadge, StatusBadge } from "./Badges";

interface OverviewTabProps {
  caseItem: CaseItem;
  tasks: TaskItem[];
  documents: DocumentItem[];
  timeline: TimelineEvent[];
  canEdit: boolean;
  isManager: boolean;
  onEditCase: () => void;
  onRiskConfirmed: (updatedCase: CaseItem) => void;
}

function cleanApprovedDisplayText(value: string | null | undefined): string {
  return cleanAIText(value).replace(/^KI[- ]Vorschlag\s*:\s*/i, "").trim();
}

function compact(value: string | null | undefined, limit = 320): string | null {
  const cleaned = cleanApprovedDisplayText(value).replace(/\s+/g, " ").trim();
  if (!cleaned) return null;
  if (cleaned.length <= limit) return cleaned;
  const cut = cleaned.slice(0, limit);
  const lastStop = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("; "));
  return `${(lastStop > 120 ? cut.slice(0, lastStop + 1) : cut).trim()}…`;
}

function SignalCard({ label, value, detail, alert = false }: { label: string; value: React.ReactNode; detail?: React.ReactNode; alert?: boolean }) {
  return <div className={`min-w-0 rounded-xl border p-4 ${alert ? "border-amber-200 bg-amber-50/60" : "border-slate-200 bg-white"}`}>
    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</p>
    <div className="mt-2 break-words text-sm font-semibold leading-6 text-slate-950">{value}</div>
    {detail ? <div className="mt-2 text-sm leading-6 text-slate-600">{detail}</div> : null}
  </div>;
}

export default function OverviewTab({ caseItem, tasks, documents, timeline, canEdit, isManager, onEditCase, onRiskConfirmed }: OverviewTabProps) {
  const [approvedSummary, setApprovedSummary] = useState<CaseAISummary | null>(null);
  const [latestApprovedSuggestion, setLatestApprovedSuggestion] = useState<AISuggestion | null>(null);
  const [confirmingRisk, setConfirmingRisk] = useState(false);
  const [riskError, setRiskError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void Promise.all([getLatestApprovedManagementSummary(caseItem.id), getCaseAISuggestions(caseItem.id)])
      .then(([summary, suggestions]) => {
        if (cancelled) return;
        setApprovedSummary(summary);
        setLatestApprovedSuggestion(
          suggestions
            .filter((item) => ["Approved", "EditedAndApproved"].includes(item.status))
            .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0] ?? null,
        );
      })
      .catch(() => {
        if (!cancelled) { setApprovedSummary(null); setLatestApprovedSuggestion(null); }
      });
    return () => { cancelled = true; };
  }, [caseItem.id, caseItem.updated_at]);

  const today = new Date(); today.setHours(0, 0, 0, 0);
  const deadline = caseItem.primary_deadline ? new Date(`${caseItem.primary_deadline}T00:00:00`) : null;
  const deadlineOverdue = Boolean(deadline && deadline < today && caseItem.status !== "Completed");
  const openTasks = tasks.filter((task) => task.status !== "Completed");
  const overdueTasks = openTasks.filter((task) => task.due_date && new Date(`${task.due_date}T00:00:00`) < today);

  // "Was ist neu?" must show an approved business development, not a raw
  // technical timeline/audit entry such as "risk: Low -> High".
  // The approved case-level management summary is the primary source because
  // it is generated from the indexed documents of the whole case.
  const latestDevelopment = compact(
    approvedSummary?.latest_development ||
    latestApprovedSuggestion?.suggested_latest_development,
    360,
  );

  // Prefer the approved case-level management recommendation. An approved
  // individual-document suggestion and the stored case action are fallbacks.
  const nextAction = cleanApprovedDisplayText(
    approvedSummary?.next_required_action ||
    latestApprovedSuggestion?.suggested_next_action ||
    caseItem.next_action,
  );

  const actionFromApprovedSummary = Boolean(approvedSummary?.next_required_action);
  const actionFromApprovedSuggestion = !actionFromApprovedSummary && Boolean(latestApprovedSuggestion?.suggested_next_action);
  const actionOrigin = actionFromApprovedSummary || actionFromApprovedSuggestion
    ? "Freigegebene KI-Empfehlung"
    : "Im Fall hinterlegte Maßnahme";
  const actionReason = actionFromApprovedSummary ? cleanApprovedDisplayText(approvedSummary?.action_justification) : "";
  // Fact citations support the underlying context; they are not automatically proof of the proposed action.
  const contextSources = actionFromApprovedSummary
    ? [...new Map((approvedSummary?.document_fact_sources ?? []).map((source) => [source.chunk_id, source])).values()]
    : [];

  const riskReason = compact(caseItem.risk_reason || caseItem.suggested_risk_reason, 240);
  const missingOwner = caseItem.status !== "Completed" && !caseItem.responsible_person?.trim();
  const missingAction = caseItem.status !== "Completed" && !nextAction;
  const isCritical = caseItem.risk === "High" || caseItem.status === "Critical" || deadlineOverdue || overdueTasks.length > 0;

  async function confirmSuggestedRisk() {
    try {
      setConfirmingRisk(true); setRiskError("");
      const response = await api.post<CaseItem>(`/cases/${caseItem.id}/confirm-risk`);
      onRiskConfirmed(response.data);
    } catch {
      setRiskError("Die Risikoeinschätzung konnte nicht übernommen werden.");
    } finally { setConfirmingRisk(false); }
  }

  return <div className="space-y-6">
    <section className={`rounded-2xl border p-6 shadow-sm ${isCritical ? "border-red-200 bg-red-50" : "border-slate-200 bg-white"}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Management-Blick</p>
          <h2 className="mt-2 text-xl font-semibold text-slate-950">Was braucht jetzt Aufmerksamkeit?</h2>
        </div>
        {canEdit && <button type="button" onClick={onEditCase} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Fall bearbeiten</button>}
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <SignalCard label="Was ist kritisch?" value={<><RiskBadge value={caseItem.risk} /> <span className="ml-2"><StatusBadge value={caseItem.status} /></span></>} detail={riskReason || (isCritical ? "Aktiver Handlungsbedarf erkannt." : "Kein akutes Warnsignal.")} alert={isCritical} />
        <SignalCard label="Was ist neu?" value={latestDevelopment || "Keine neue bestätigte Entwicklung"} />
        <div className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 md:col-span-2 xl:col-span-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Nächste Maßnahme</p>
          {caseItem.status === "Completed" ? (
            <p className="mt-2 text-sm font-semibold text-slate-900">Fall abgeschlossen</p>
          ) : nextAction ? (
            <div className="mt-2 space-y-3">
              <p className="break-words text-sm font-semibold leading-6 text-slate-950">{compact(nextAction, 150)}</p>
              {cleanApprovedDisplayText(nextAction).length > 150 && (
                <details className="text-sm text-slate-700">
                  <summary className="cursor-pointer font-medium text-slate-600">Vollständige Maßnahme anzeigen</summary>
                  <p className="mt-2 whitespace-pre-wrap break-words leading-6">{cleanApprovedDisplayText(nextAction)}</p>
                </details>
              )}
              {actionReason && <div className="border-t border-slate-100 pt-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Begründung</p>
                <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{actionReason}</p>
              </div>}
              {contextSources.length > 0 && <details className="border-t border-slate-100 pt-3 text-xs text-slate-600">
                <summary className="cursor-pointer font-medium">Belege zum Fallkontext anzeigen ({contextSources.length})</summary>
                <ul className="mt-2 space-y-2">
                  {contextSources.map((source) => <li key={source.chunk_id} className="rounded-lg bg-slate-50 p-2">
                    <span className="font-medium text-slate-800">{source.file_name}</span>
                    {source.page_number != null && <span> · Seite {source.page_number}</span>}
                    {source.document_date && <span> · {source.document_date}</span>}
                  </li>)}
                </ul>
                <p className="mt-2">Diese Fundstellen belegen Fallfakten; die Empfehlung selbst ist eine fachlich zu prüfende Ableitung.</p>
              </details>}
              <p className="border-t border-slate-100 pt-2 text-xs text-slate-500">
                {actionOrigin} · {actionFromApprovedSummary || actionFromApprovedSuggestion ? "KI-Vorschlag freigegeben" : "Freigabestatus nicht gesondert ausgewiesen"} · Keine Aufgabe erstellt
              </p>
            </div>
          ) : <p className="mt-2 text-sm text-slate-600">Nicht definiert</p>}
        </div>
        <SignalCard label="Verantwortlich" value={caseItem.responsible_person?.trim() || "Nicht zugewiesen"} alert={missingOwner} />
        <SignalCard label="Relevante Frist" value={caseItem.status === "Completed" ? "Keine offene Frist" : caseItem.primary_deadline || "Keine klare Frist"} detail={deadlineOverdue ? "Frist ist überfällig." : undefined} alert={deadlineOverdue} />
      </div>
    </section>

    {(deadlineOverdue || overdueTasks.length > 0 || missingOwner || missingAction) && <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
      <h3 className="font-semibold text-amber-950">Offener Handlungsbedarf</h3>
      <div className="mt-3 flex flex-wrap gap-2 text-sm text-amber-950">
        {deadlineOverdue && <span className="rounded-lg bg-white px-3 py-2">Hauptfrist überfällig</span>}
        {overdueTasks.length > 0 && <span className="rounded-lg bg-white px-3 py-2">{overdueTasks.length} Aufgabe(n) überfällig</span>}
        {missingOwner && <span className="rounded-lg bg-white px-3 py-2">Verantwortung offen</span>}
        {missingAction && <span className="rounded-lg bg-white px-3 py-2">Nächste Maßnahme offen</span>}
      </div>
    </section>}

    <section className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Kurzkontext</p>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">{compact(caseItem.management_summary || caseItem.description, 700) || "Noch keine bestätigte Zusammenfassung vorhanden."}</p>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Arbeitsstand</p>
        <dl className="mt-3 space-y-3 text-sm">
          <div className="flex justify-between gap-4"><dt className="text-slate-500">Offene Aufgaben</dt><dd className="font-semibold">{openTasks.length}</dd></div>
          <div className="flex justify-between gap-4"><dt className="text-slate-500">Dokumente</dt><dd className="font-semibold">{documents.length}</dd></div>
          <div className="flex justify-between gap-4"><dt className="text-slate-500">Verlaufseinträge</dt><dd className="font-semibold">{timeline.length}</dd></div>
        </dl>
      </div>
    </section>

    {caseItem.suggested_risk && caseItem.suggested_risk !== caseItem.risk && <section className="rounded-2xl border border-blue-200 bg-blue-50 p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><p className="text-xs font-semibold uppercase text-blue-600">KI-Vorschlag zur Risikobewertung</p><div className="mt-2"><RiskBadge value={caseItem.suggested_risk} /></div><p className="mt-2 text-sm text-blue-900">{compact(caseItem.suggested_risk_reason, 320) || "Keine Begründung vorhanden."}</p></div>
        {isManager && <button disabled={confirmingRisk} onClick={() => void confirmSuggestedRisk()} className="rounded-xl bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{confirmingRisk ? "Wird übernommen…" : "Risiko übernehmen"}</button>}
      </div>
      {riskError && <p className="mt-3 text-sm text-red-700">{riskError}</p>}
    </section>}
  </div>;
}
