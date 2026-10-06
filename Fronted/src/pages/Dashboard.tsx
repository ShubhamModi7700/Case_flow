import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { type DashboardData, formatCaseNumber } from "../types";

const PREVIEW_MAX = 150;

function compact(value: string | null | undefined, fallback: string) {
  const text = value?.replace(/\s+/g, " ").trim();
  if (!text) return fallback;
  return text.length > PREVIEW_MAX ? `${text.slice(0, PREVIEW_MAX).trim()}…` : text;
}

function formatDeadline(value: string | null) {
  if (!value) return "Keine Frist";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("de-DE");
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<DashboardData>("/dashboard/summary")
      .then((response) => setData(response.data))
      .catch((requestError) => {
        console.error(requestError);
        setError("Die Übersicht konnte nicht geladen werden. Bitte prüfen Sie, ob das Backend läuft.");
      });
  }, []);

  if (error) return <div className="p-8"><div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div></div>;
  if (!data) return <div className="p-8 text-slate-500">Übersicht wird geladen...</div>;

  return (
    <div className="mx-auto max-w-7xl p-8">
      <header className="mb-7 flex items-start justify-between gap-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Case Flow</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-950">Management Cockpit</h1>
          <p className="mt-2 text-sm text-slate-500">Auf einen Blick: Wo besteht Handlungsbedarf?</p>
        </div>
        <Link to="/cases/new" className="shrink-0 rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800">+ Fall anlegen</Link>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <AttentionCard to="/cases?risk=High" title="Kritisch" value={data.high_risk_cases} hint="Fälle mit hohem Risiko" tone="red" />
        <AttentionCard to="/cases?overdue=true" title="Überfällig" value={data.overdue_deadlines} hint="Fristen mit sofortigem Handlungsbedarf" tone="amber" />
        <AttentionCard to="/cases?missing_owner=true" title="Ohne Verantwortlichen" value={data.cases_without_responsible} hint="Zuständigkeit festlegen" />
        <AttentionCard to="/cases?missing_next_action=true" title="Ohne nächste Maßnahme" value={data.cases_without_next_action} hint="Nächsten Schritt festlegen" />
      </div>

      <section className="mt-7 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-4 border-b border-slate-100 px-6 py-5">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Handlungsbedarf</h2>
            <p className="mt-1 text-sm text-slate-500">Priorisiert nach überfälliger Frist, hohem Risiko und fehlenden Angaben.</p>
          </div>
          <Link to="/cases?status_group=open" className="text-sm font-medium text-slate-600 hover:text-slate-950">Alle offenen Fälle</Link>
        </div>

        {!data.attention_items.length ? (
          <p className="m-6 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Aktuell besteht kein hervorgehobener Handlungsbedarf.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr><th className="px-6 py-3">Fall</th><th className="px-4 py-3">Warum Handlungsbedarf?</th><th className="px-4 py-3">Nächste Maßnahme</th><th className="px-4 py-3">Verantwortlich</th><th className="px-6 py-3">Frist</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.attention_items.map((item) => (
                  <tr key={item.case_id} className="align-top hover:bg-slate-50">
                    <td className="px-6 py-4"><Link to={`/cases/${item.case_id}`} className="font-semibold text-slate-950 hover:underline">{formatCaseNumber(item.case_id)} — {item.title}</Link></td>
                    <td className="px-4 py-4"><span className={item.risk === "High" ? "font-medium text-red-700" : "font-medium text-slate-700"}>{item.reason}</span></td>
                    <td className="max-w-md px-4 py-4 leading-6 text-slate-600">{compact(item.next_action, "Noch nicht festgelegt")}</td>
                    <td className="px-4 py-4 text-slate-700">{item.responsible_person?.trim() || "Nicht zugewiesen"}</td>
                    <td className="whitespace-nowrap px-6 py-4 font-medium text-slate-700">{formatDeadline(item.deadline)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-500">
        <span><strong className="text-slate-800">{data.open_cases}</strong> offene Fälle</span>
        <span><strong className="text-slate-800">{data.upcoming_deadlines}</strong> Fristen in 7 Tagen</span>
        <span><strong className="text-slate-800">{data.pending_ai_suggestions + data.pending_management_summaries}</strong> KI-Vorschläge zur Prüfung</span>
      </div>
    </div>
  );
}

type AttentionCardProps = { to: string; title: string; value: number; hint: string; tone?: "red" | "amber" | "neutral" };
function AttentionCard({ to, title, value, hint, tone = "neutral" }: AttentionCardProps) {
  const classes = tone === "red" ? "border-red-200 bg-red-50 text-red-800" : tone === "amber" ? "border-amber-200 bg-amber-50 text-amber-900" : "border-slate-200 bg-white text-slate-950";
  return <Link to={to} className={`rounded-2xl border p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${classes}`}><p className="text-xs font-semibold uppercase tracking-wider">{title}</p><p className="mt-3 text-4xl font-bold">{value}</p><p className="mt-2 text-sm opacity-75">{hint}</p></Link>;
}
