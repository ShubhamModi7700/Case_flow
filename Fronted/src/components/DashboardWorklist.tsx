import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { formatCaseNumber } from "../types";
import type { DashboardWorklistData } from "../types/dashboard";

function formatDate(value: string | null, fallback: string) {
  if (!value) return fallback;
  return new Date(`${value}T00:00:00`).toLocaleDateString("de-DE");
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

  const items = data ? (view === "today" ? data.today_items : data.next_seven_days_items) : [];
  return (
    <section aria-labelledby="worklist-heading" className="mt-7 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-6 py-5">
        <h2 id="worklist-heading" className="text-lg font-semibold text-slate-950">Aufgaben und nächste Schritte</h2>
        <div className="mt-3 flex gap-2" role="group" aria-label="Zeitraum">
          {([ ["today", "Heute"], ["week", "Nächste 7 Tage"] ] as const).map(([value, label]) => (
            <button key={value} type="button" aria-pressed={view === value} onClick={() => setView(value)} className={`rounded-lg px-4 py-2 text-sm font-semibold ${view === value ? "bg-slate-950 text-white" : "bg-slate-100 text-slate-700"}`}>{label}</button>
          ))}
        </div>
        {data && <p className="mt-3 text-xs text-slate-500">
          {formatDate(data.today, "")} – {formatDate(view === "today" ? data.today : data.through, "")} ({data.timezone}).
          {" "}Inklusive überfälliger und dringender Arbeit. Vorbereitung: {data.preparation_lead_days} Kalendertage vor der Frist (vorläufige Planungsregel; keine neue Frist).
        </p>}
      </div>
      {error ? <p role="alert" className="p-6 text-sm text-red-700">Die Aufgabenübersicht konnte nicht geladen werden.</p>
        : !data ? <p role="status" className="p-6 text-sm text-slate-500">Aufgabenübersicht wird geladen…</p>
        : !items.length ? <p role="status" className="p-6 text-sm text-slate-500">Keine Aufgaben mit Handlungsbedarf in diesem Zeitraum.</p>
        : <div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-left text-sm">
          <caption className="sr-only">{view === "today" ? "Heute" : "Nächste 7 Tage"}: priorisierte Aufgaben und Fallmaßnahmen</caption>
          <thead className="bg-slate-50 text-xs font-semibold text-slate-500"><tr>
            {["Fall", "Aufgabe", "Verantwortlich", "Frist", "Vorbereitung ab", "Warum priorisiert?", "Nächste Maßnahme"].map(label => <th key={label} scope="col" className="px-4 py-3">{label}</th>)}
          </tr></thead>
          <tbody className="divide-y divide-slate-100">{items.map(item => <tr key={item.key} className="align-top hover:bg-slate-50">
            <td className="px-4 py-4"><Link className="font-semibold text-slate-950 hover:underline" to={`/cases/${item.case_id}`}>{formatCaseNumber(item.case_id)} — {item.case_title}</Link></td>
            <td className="px-4 py-4 text-slate-700">{item.title}<span className="mt-1 block text-xs text-slate-500">{item.kind === "task" ? "Aufgabe" : "Fallmaßnahme"}</span></td>
            <td className="px-4 py-4">{item.responsible_person || "Nicht zugewiesen"}</td>
            <td className="whitespace-nowrap px-4 py-4">{formatDate(item.deadline, "Keine Frist")}</td>
            <td className="whitespace-nowrap px-4 py-4">{formatDate(item.preparation_date, "Nicht berechenbar")}</td>
            <td className={`px-4 py-4 ${item.priority === "overdue" ? "text-red-700" : item.priority === "urgent" ? "text-amber-800" : "text-slate-700"}`}>{item.reasons.join(" · ")}</td>
            <td className="px-4 py-4 text-slate-700">{item.next_action}</td>
          </tr>)}</tbody>
        </table></div>}
    </section>
  );
}
