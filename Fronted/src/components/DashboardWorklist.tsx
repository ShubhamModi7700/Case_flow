import { useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { formatCaseNumber } from "../types";
import type { DashboardWorkItem, DashboardWorklistData } from "../types/dashboard";

function formatDate(value: string | null) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("de-DE");
}

function priorityLabel(item: DashboardWorkItem) {
  if (item.priority === "overdue") return "Überfällig";
  if (item.priority === "urgent") return "Dringend";
  return "Anstehend";
}

const ACTION_PREVIEW_LENGTH = 280;

function actionPreview(text: string) {
  if (text.length <= ACTION_PREVIEW_LENGTH) return text;
  const prefix = text.slice(0, ACTION_PREVIEW_LENGTH);
  const sentenceEnds = [...prefix.matchAll(/[.!?](?=\s|$)/g)];
  const sentenceEnd = sentenceEnds.at(-1)?.index;
  const end = sentenceEnd !== undefined ? sentenceEnd + 1 : prefix.lastIndexOf(" ");
  return `${prefix.slice(0, end > 0 ? end : prefix.length).trimEnd()}…`;
}

function WorkItemCard({ item }: { item: DashboardWorkItem }) {
  const [showDetails, setShowDetails] = useState(false);
  const [showFullAction, setShowFullAction] = useState(false);
  const actionId = useId();
  const reasonsId = useId();
  const deadline = formatDate(item.deadline);
  const preparation = formatDate(item.preparation_date);
  const attention = formatDate(item.attention_date);
  const attentionReasons = item.attention_reasons?.length ? item.attention_reasons : item.reasons;
  const isGenericTitle = /^(Fallmaßnahme\s*\/\s*Wiedervorlage|Fallmaßnahme|Wiedervorlage)$/i.test(item.title.trim());
  const action = item.next_action?.trim() ? item.next_action : "Nächste Maßnahme festlegen";
  const preview = actionPreview(action);
  const title = !isGenericTitle && item.title.trim() ? item.title : "Nächste Maßnahme";
  const badgeClass = item.priority === "overdue"
    ? "bg-red-50 text-red-700 ring-red-200"
    : item.priority === "urgent"
      ? "bg-amber-50 text-amber-800 ring-amber-200"
      : "bg-slate-100 text-slate-700 ring-slate-200";

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <Link to={`/cases/${item.case_id}`} className="text-sm font-semibold text-slate-950 hover:underline">
            {formatCaseNumber(item.case_id)} — {item.case_title}
          </Link>
          <h4 className="mt-2 text-sm font-semibold text-slate-800">{title}</h4>
        </div>
        <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ring-1 ${badgeClass}`}>
          {priorityLabel(item)}
        </span>
      </div>

      {attentionReasons.length > 0 && <p className="mt-3 text-xs leading-5 text-slate-600">
        <span className="font-semibold text-slate-800">Handlungsanlass:</span> {attentionReasons.join(" · ")}
      </p>}

      <p id={actionId} className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">
        {showFullAction ? action : preview}
      </p>
      {preview !== action && <button
        type="button"
        aria-expanded={showFullAction}
        aria-controls={actionId}
        onClick={() => setShowFullAction(value => !value)}
        className="mt-2 text-xs font-medium text-slate-600 underline-offset-2 hover:text-slate-950 hover:underline"
      >
        {showFullAction ? "Weniger anzeigen" : "Vollständige Maßnahme anzeigen"}
      </button>}

      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-100 pt-3 text-xs text-slate-600">
        <span><span className="font-semibold text-slate-800">Verantwortlich:</span> {item.responsible_person || "Nicht zugewiesen"}</span>
        {attention && <span><span className="font-semibold text-slate-800">Handlungsdatum:</span> {attention}</span>}
        <span><span className="font-semibold text-slate-800">Frist:</span> {deadline || "Keine Frist"}</span>
        {preparation && <span><span className="font-semibold text-slate-800">Vorbereitungsbeginn:</span> {preparation}</span>}
      </div>

      {item.reasons.length > 0 && (
        <div className="mt-3">
          <button
            type="button"
            aria-expanded={showDetails}
            aria-controls={reasonsId}
            onClick={() => setShowDetails(value => !value)}
            className="text-xs font-medium text-slate-600 underline-offset-2 hover:text-slate-950 hover:underline"
          >
            {showDetails ? "Priorisierungsgründe ausblenden" : `Handlungsgrund (${item.reasons.length})`}
          </button>
          {showDetails && (
            <ul id={reasonsId} className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-slate-600">
              {item.reasons.map((reason, index) => <li key={`${item.key}-${index}`}>{reason}</li>)}
            </ul>
          )}
        </div>
      )}
    </article>
  );
}

function WorkItemList({ items, emptyMessage }: { items: DashboardWorkItem[]; emptyMessage: string }) {
  if (!items.length) return <p className="py-4 text-sm text-slate-500">{emptyMessage}</p>;
  return <div className="grid gap-3">{items.map(item => <WorkItemCard key={item.key} item={item} />)}</div>;
}

export default function DashboardWorklist() {
  const [data, setData] = useState<DashboardWorklistData | null>(null);
  const [error, setError] = useState(false);
  const [view, setView] = useState<"today" | "week">("today");

  useEffect(() => {
    let active = true;
    api.get<DashboardWorklistData>("/dashboard/worklist")
      .then(response => { if (active) setData(response.data); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, []);

  const todayItems = data?.today_items ?? [];
  const weekItems = data?.next_seven_days_items ?? [];
  const todayKeys = new Set(todayItems.map(item => item.key));
  const upcomingItems = weekItems.filter(item => !todayKeys.has(item.key));

  return (
    <section aria-labelledby="worklist-heading" className="mt-7 rounded-2xl border border-slate-200 bg-slate-50/60 p-4 shadow-sm sm:p-6">
      <div className="mb-5">
        <h2 id="worklist-heading" className="text-lg font-semibold text-slate-950">Priorisierte Maßnahmen</h2>
        <p className="mt-1 text-sm text-slate-500">Priorisierte Maßnahmen über alle Fälle hinweg</p>
        <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Zeitraum">
          {([ ["today", "Heute", todayItems.length], ["week", "Kommende 7 Tage", upcomingItems.length] ] as const).map(([value, label, count]) => (
            <button key={value} type="button" aria-pressed={view === value} onClick={() => setView(value)} className={`rounded-lg px-4 py-2 text-sm font-semibold ${view === value ? "bg-slate-950 text-white" : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100"}`}>
              {label} <span className="ml-1 opacity-75">({data ? count : "…"})</span>
            </button>
          ))}
        </div>
        {data && <p className="mt-3 text-xs leading-5 text-slate-500">
          Stand: {formatDate(data.today)} · {view === "week" ? `Bis ${formatDate(data.through)} · ` : ""}
          Vorbereitungsbeginn {data.preparation_lead_days} Kalendertage vor Frist (Planungsregel, keine neue Frist).
        </p>}
      </div>
      {error ? <p role="alert" className="rounded-xl bg-white p-5 text-sm text-red-700">Die Aufgabenübersicht konnte nicht geladen werden.</p>
        : !data ? <p role="status" className="rounded-xl bg-white p-5 text-sm text-slate-500">Aufgabenübersicht wird geladen…</p>
        : view === "today" ? (
          <WorkItemList items={todayItems} emptyMessage="Keine Maßnahmen mit Handlungsbedarf heute." />
        ) : (
          <div>
            <h3 className="mb-2 text-sm font-semibold text-slate-900">Zusätzliche Maßnahmen in den kommenden 7 Tagen ({upcomingItems.length})</h3>
            <p className="mb-4 text-xs leading-5 text-slate-500">Nur zusätzliche Maßnahmen ab morgen. Überfällige und bereits heute anstehende Maßnahmen stehen unter „Heute“.</p>
            <WorkItemList items={upcomingItems} emptyMessage="Keine zusätzlichen Maßnahmen in den kommenden sieben Tagen. Alle derzeit anstehenden Maßnahmen finden Sie unter „Heute“." />
          </div>
        )}
    </section>
  );
}
