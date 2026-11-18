import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { formatCaseNumber } from "../types";
import type { DashboardWorkItem, DashboardWorklistData } from "../types/dashboard";

function formatDate(value: string | null, fallback: string) {
  if (!value) return fallback;
  return new Date(`${value}T00:00:00`).toLocaleDateString("de-DE");
}

function WorklistTable({ items, caption }: { items: DashboardWorkItem[]; caption: string }) {
  if (!items.length) {
    return <p className="px-6 py-5 text-sm text-slate-500">Keine Aufgaben in diesem Abschnitt.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1100px] text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-slate-50 text-xs font-semibold text-slate-500">
          <tr>{["Fall", "Aufgabe", "Verantwortlich", "Frist", "Vorbereitung ab", "Warum priorisiert?", "Nächste Maßnahme"].map(label => (
            <th key={label} scope="col" className="px-4 py-3">{label}</th>
          ))}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {items.map(item => (
            <tr key={item.key} className="align-top hover:bg-slate-50">
              <td className="px-4 py-4"><Link className="font-semibold text-slate-950 hover:underline" to={`/cases/${item.case_id}`}>{formatCaseNumber(item.case_id)} — {item.case_title}</Link></td>
              <td className="px-4 py-4 text-slate-700">{item.title}<span className="mt-1 block text-xs text-slate-500">{item.kind === "task" ? "Aufgabe" : "Fallmaßnahme"}</span></td>
              <td className="px-4 py-4">{item.responsible_person || "Nicht zugewiesen"}</td>
              <td className="whitespace-nowrap px-4 py-4">{formatDate(item.deadline, "Keine Frist")}</td>
              <td className="whitespace-nowrap px-4 py-4">{formatDate(item.preparation_date, "Nicht berechenbar")}</td>
              <td className={`px-4 py-4 ${item.priority === "overdue" ? "text-red-700" : item.priority === "urgent" ? "text-amber-800" : "text-slate-700"}`}>{item.reasons.join(" · ")}</td>
              <td className="px-4 py-4 text-slate-700">{item.next_action}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
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
    <section aria-labelledby="worklist-heading" className="mt-7 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-6 py-5">
        <h2 id="worklist-heading" className="text-lg font-semibold text-slate-950">Aufgaben und nächste Schritte</h2>
        <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Zeitraum">
          {([ ["today", "Heute", todayItems.length], ["week", "Nächste 7 Tage", weekItems.length] ] as const).map(([value, label, count]) => (
            <button key={value} type="button" aria-pressed={view === value} onClick={() => setView(value)} className={`rounded-lg px-4 py-2 text-sm font-semibold ${view === value ? "bg-slate-950 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>
              {label} <span className="ml-1 opacity-75">({data ? count : "…"})</span>
            </button>
          ))}
        </div>
        {data && <p className="mt-3 text-xs text-slate-500">
          {formatDate(data.today, "")} – {formatDate(view === "today" ? data.today : data.through, "")} ({data.timezone}).
          {" "}Inklusive überfälliger und dringender Arbeit. Vorbereitung: {data.preparation_lead_days} Kalendertage vor der Frist (vorläufige Planungsregel; keine neue Frist).
        </p>}
      </div>
      {error ? <p role="alert" className="p-6 text-sm text-red-700">Die Aufgabenübersicht konnte nicht geladen werden.</p>
        : !data ? <p role="status" className="p-6 text-sm text-slate-500">Aufgabenübersicht wird geladen…</p>
        : view === "today" ? (
          todayItems.length ? <WorklistTable items={todayItems} caption="Heute: priorisierte Aufgaben und Fallmaßnahmen" />
            : <p role="status" className="p-6 text-sm text-slate-500">Keine Aufgaben mit Handlungsbedarf heute.</p>
        ) : (
          <div>
            <div className="border-b border-slate-100 bg-slate-50/50 px-6 py-4">
              <h3 className="font-semibold text-slate-900">Jetzt erledigen ({todayItems.length})</h3>
              <p className="mt-1 text-xs text-slate-500">Bereits fällige, überfällige oder dringende Arbeit.</p>
            </div>
            <WorklistTable items={todayItems} caption="Nächste 7 Tage: Jetzt erledigen" />
            <div className="border-y border-slate-100 bg-slate-50/50 px-6 py-4">
              <h3 className="font-semibold text-slate-900">Später diese Woche ({upcomingItems.length})</h3>
              <p className="mt-1 text-xs text-slate-500">Arbeit, deren Handlungsbedarf erst innerhalb der nächsten sieben Tage beginnt.</p>
            </div>
            <WorklistTable items={upcomingItems} caption="Nächste 7 Tage: Später diese Woche" />
          </div>
        )}
    </section>
  );
}
