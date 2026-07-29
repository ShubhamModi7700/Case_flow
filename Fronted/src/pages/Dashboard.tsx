import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { riskConfig } from "../utils/riskStyles";
import {
  type DashboardData,
  formatCaseNumber,
} from "../types";

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadDashboard() {
      try {
        const response =
          await api.get<DashboardData>("/dashboard/summary");

        setData(response.data);
      } catch (requestError) {
        console.error(requestError);

        setError(
          "Die Übersicht konnte nicht geladen werden. Bitte prüfen Sie, ob das Backend läuft.",
        );
      }
    }

    void loadDashboard();
  }, []);

  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
          {error}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-8 text-slate-500">
        Übersicht wird geladen...
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl p-8">
      <header className="mb-8 flex items-start justify-between gap-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
            Case Flow
          </p>

          <h1 className="mt-2 text-3xl font-bold text-slate-950">
            Management-Übersicht
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            Wo müssen wir jetzt handeln?
          </p>
        </div>

        <Link
          to="/cases/new"
          className="shrink-0 rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800"
        >
          + Fall anlegen
        </Link>
      </header>

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        <DashboardCard
          to="/cases?status_group=open"
          title="Offene Fälle"
          value={data.open_cases}
          description="Alle aktiven Fälle"
        />

        <DashboardCard
          to="/cases?risk=High"
          title="Hohes Risiko"
          value={data.high_risk_cases}
          description="Sofortige Aufmerksamkeit erforderlich"
          containerClass={riskConfig.High.cardClass}
          textClass={riskConfig.High.textClass}
        />

        <DashboardCard
          to="/cases?risk=Medium"
          title="Mittleres Risiko"
          value={data.medium_risk_cases}
          description="Zeitnahe Prüfung empfohlen"
          containerClass={riskConfig.Medium.cardClass}
          textClass={riskConfig.Medium.textClass}
        />

        <DashboardCard
          to="/cases?risk=Low"
          title="Niedriges Risiko"
          value={data.low_risk_cases}
          description="Derzeit kein unmittelbarer Handlungsbedarf"
          containerClass={riskConfig.Low.cardClass}
          textClass={riskConfig.Low.textClass}
        />

        <DashboardCard
          to="/cases?overdue=true"
          title="Überfällige Fristen"
          value={data.overdue_deadlines}
          description="Fälle mit überfälligen Aufgaben oder Fristen"
          containerClass="border-red-200 bg-red-50"
          textClass="text-red-700"
        />

        <DashboardCard
          to="/cases?upcoming=true"
          title="Anstehende Fristen"
          value={data.upcoming_deadlines}
          description="Innerhalb der nächsten sieben Tage"
          containerClass="border-amber-200 bg-amber-50"
          textClass="text-amber-700"
        />

        <DashboardCard
          to="/cases?missing_owner=true"
          title="Ohne verantwortliche Person"
          value={data.cases_without_responsible}
          description="Zuweisung erforderlich"
        />

        <DashboardCard
          to="/cases?missing_next_action=true"
          title="Ohne nächste Maßnahme"
          value={data.cases_without_next_action}
          description="Nächsten Schritt festlegen"
        />
      </div>

      <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">
              Nächste fällige Maßnahmen
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              Maßnahmen mit Frist innerhalb der nächsten sieben Tage.
            </p>
          </div>

          <Link
            to="/cases?upcoming=true"
            className="shrink-0 text-sm font-medium text-slate-600 hover:text-slate-950"
          >
            Alle anzeigen
          </Link>
        </div>

        {!data.next_due_actions.length ? (
          <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">
            In den nächsten sieben Tagen sind keine Maßnahmen fällig.
          </p>
        ) : (
          <div className="mt-4 divide-y divide-slate-100">
            {data.next_due_actions.map((action) => (
              <Link
                key={action.case_id}
                to={`/cases/${action.case_id}`}
                className="flex items-center justify-between gap-4 rounded-lg py-4 hover:bg-slate-50"
              >
                <div>
                  <p className="font-medium text-slate-950">
                    {formatCaseNumber(action.case_id)} — {action.title}
                  </p>

                  <p className="mt-1 text-sm text-slate-500">
                    {action.next_action}
                  </p>
                </div>

                <span className="shrink-0 text-sm text-slate-500">
                  {action.deadline ?? "Keine Frist"}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

type DashboardCardProps = {
  to: string;
  title: string;
  value: number;
  description: string;
  containerClass?: string;
  textClass?: string;
};

function DashboardCard({
  to,
  title,
  value,
  description,
  containerClass = "border-slate-200 bg-white",
  textClass = "text-slate-950",
}: DashboardCardProps) {
  const descriptionClass =
    textClass === "text-slate-950"
      ? "text-slate-500"
      : textClass;

  return (
    <Link
      to={to}
      className={`block rounded-2xl border p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-slate-400 ${containerClass}`}
    >
      <p
        className={`text-xs font-semibold uppercase tracking-wider ${textClass}`}
      >
        {title}
      </p>

      <p className={`mt-4 text-4xl font-bold ${textClass}`}>
        {value}
      </p>

      <p className={`mt-2 text-sm ${descriptionClass}`}>
        {description}
      </p>
    </Link>
  );
}