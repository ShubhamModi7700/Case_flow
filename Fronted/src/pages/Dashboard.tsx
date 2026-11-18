import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { type DashboardData } from "../types";
import DashboardWorklist from "../components/DashboardWorklist";

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
          <h1 className="mt-2 text-3xl font-bold text-slate-950">Meine Übersicht</h1>
          <p className="mt-2 text-sm text-slate-500">Was muss heute erledigt werden?</p>
        </div>
        <Link to="/cases/new" className="shrink-0 rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800">+ Fall anlegen</Link>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <AttentionCard to="/cases?risk=High" title="Kritisch" value={data.high_risk_cases} hint="Fälle mit hohem Risiko" tone="red" />
        <AttentionCard to="/cases?overdue=true" title="Überfällig" value={data.overdue_deadlines} hint="Fristen mit sofortigem Handlungsbedarf" tone="amber" />
        <AttentionCard to="/cases?missing_owner=true" title="Ohne Zuständigkeit" value={data.cases_without_responsible} hint="Zuständigkeit festlegen" />
        <AttentionCard to="/cases?missing_next_action=true" title="Maßnahme fehlt" value={data.cases_without_next_action} hint="Nächste Maßnahme festlegen" />
      </div>

      <DashboardWorklist />

      <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-500">
        <span><strong className="text-slate-800">{data.open_cases}</strong> offene Fälle</span>
        <span><strong className="text-slate-800">{data.upcoming_deadlines}</strong> Fristen in 7 Tagen</span>
        <span><strong className="text-slate-800">{data.pending_ai_suggestions + data.pending_management_summaries}</strong> Vorschläge zur Prüfung</span>
      </div>
    </div>
  );
}

type AttentionCardProps = { to: string; title: string; value: number; hint: string; tone?: "red" | "amber" | "neutral" };
function AttentionCard({ to, title, value, hint, tone = "neutral" }: AttentionCardProps) {
  const classes = tone === "red" ? "border-red-200 bg-red-50 text-red-800" : tone === "amber" ? "border-amber-200 bg-amber-50 text-amber-900" : "border-slate-200 bg-white text-slate-950";
  return <Link to={to} className={`rounded-2xl border p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${classes}`}><p className="text-xs font-semibold uppercase tracking-wider">{title}</p><p className="mt-3 text-4xl font-bold">{value}</p><p className="mt-2 text-sm opacity-75">{hint}</p></Link>;
}
