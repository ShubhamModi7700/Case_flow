import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import {
  type DashboardData,
  formatCaseNumber,
} from "../types";

export default function Dashboard() {
  const [data, setData] =
    useState<DashboardData | null>(null);

  const [error, setError] = useState("");

  useEffect(() => {
    async function loadDashboard() {
      try {
        const response =
          await api.get<DashboardData>(
            "/dashboard/summary",
          );

        setData(response.data);
      } catch (requestError) {
        console.error(requestError);

        setError(
          "Dashboard data could not be loaded. Check whether FastAPI is running.",
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
        Loading dashboard...
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl p-8">
      <header className="mb-8 flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
            Case Flow
          </p>

          <h1 className="mt-2 text-3xl font-bold text-slate-950">
            Management overview
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            Current cases, risk levels, actions and deadlines.
          </p>
        </div>

        <Link
          to="/cases/new"
          className="rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800"
        >
          + Create case
        </Link>
      </header>

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">

        <MetricCard
          title="Open cases"
          value={data.open_cases}
          description="Active cases"
        />

        <MetricCard
          title="Completed cases"
          value={data.completed_cases}
          description="Successfully closed cases"
        />

        <RiskCard
          title="Low risk"
          value={data.low_risk_cases}
          description="Active low-risk cases"
          containerClass="border-green-200 bg-green-50"
          textClass="text-green-700"
        />

        <RiskCard
          title="Medium risk"
          value={data.medium_risk_cases}
          description="Cases requiring attention"
          containerClass="border-amber-200 bg-amber-50"
          textClass="text-amber-700"
        />

        <RiskCard
          title="High risk"
          value={data.high_risk_cases}
          description="Cases requiring immediate attention"
          containerClass="border-red-200 bg-red-50"
          textClass="text-red-700"
        />

        <MetricCard
          title="Overdue deadlines"
          value={data.overdue_deadlines}
          description="Open tasks past due"
        />

        <MetricCard
          title="Upcoming deadlines"
          value={data.upcoming_deadlines}
          description="Due within seven days"
        />

        <MetricCard
          title="Without responsible person"
          value={data.cases_without_responsible}
          description="Cases requiring assignment"
        />

        <MetricCard
          title="Without next action"
          value={data.cases_without_next_action}
          description="Cases missing a next step"
        />

      </div>

      <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">
              Next due actions
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              Actions due during the next seven days.
            </p>
          </div>

          <Link
            to="/cases"
            className="text-sm font-medium text-slate-600 hover:text-slate-950"
          >
            View all cases
          </Link>
        </div>

        {!data.next_due_actions.length ? (
          <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">
            No actions are due within seven days.
          </p>
        ) : (
          <div className="mt-4 divide-y divide-slate-100">
            {data.next_due_actions.map((action) => (
              <Link
                key={action.case_id}
                to={`/cases/${action.case_id}`}
                className="flex items-center justify-between gap-4 py-4 hover:bg-slate-50"
              >
                <div>
                  <p className="font-medium text-slate-950">
                    {formatCaseNumber(action.case_id)}
                    {" — "}
                    {action.title}
                  </p>

                  <p className="mt-1 text-sm text-slate-500">
                    {action.next_action}
                  </p>
                </div>

                <span className="text-sm text-slate-500">
                  {action.deadline ?? "No deadline"}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function MetricCard({
  title,
  value,
  description,
}: {
  title: string;
  value: number;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        {title}
      </p>

      <p className="mt-4 text-4xl font-bold text-slate-950">
        {value}
      </p>

      <p className="mt-2 text-sm text-slate-500">
        {description}
      </p>
    </div>
  );
}

function RiskCard({
  title,
  value,
  description,
  containerClass,
  textClass,
}: {
  title: string;
  value: number;
  description: string;
  containerClass: string;
  textClass: string;
}) {
  return (
    <div
      className={`rounded-2xl border p-6 shadow-sm ${containerClass}`}
    >
      <p
        className={`text-xs font-semibold uppercase tracking-wider ${textClass}`}
      >
        {title}
      </p>

      <p
        className={`mt-4 text-4xl font-bold ${textClass}`}
      >
        {value}
      </p>

      <p className={`mt-2 text-sm ${textClass}`}>
        {description}
      </p>
    </div>
  );
}