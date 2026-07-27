import type { CaseItem } from "../../types";
import { formatDateTime } from "./formatters";

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</dt>
      <dd className="mt-2 text-sm text-slate-800">{value}</dd>
    </div>
  );
}

export default function OverviewTab({ caseItem }: { caseItem: CaseItem }) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
        <h2 className="text-lg font-semibold text-slate-950">Case information</h2>
        <dl className="mt-6 grid gap-6 sm:grid-cols-2">
          <Detail label="Title" value={caseItem.title} />
          <Detail label="Category" value={caseItem.category} />
          <Detail label="Company" value={caseItem.company} />
          <Detail label="Department" value={caseItem.department ?? "Not provided"} />
          <Detail label="External contact" value={caseItem.external_contact ?? "Not provided"} />
          <Detail label="Responsible person" value={caseItem.responsible_person ?? "Not assigned"} />
          <Detail label="Status" value={caseItem.status} />
          <Detail label="Risk" value={caseItem.risk} />
          <Detail label="Primary deadline" value={caseItem.primary_deadline ?? "Not defined"} />
          <Detail label="Follow-up date" value={caseItem.follow_up_date ?? "Not defined"} />
          <Detail label="Created" value={formatDateTime(caseItem.created_at)} />
          <Detail label="Last updated" value={formatDateTime(caseItem.updated_at)} />
        </dl>
      </section>

      <section className="space-y-6">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-950">Next action</h2>
          <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-600">{caseItem.next_action ?? "No next action defined."}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-950">Description</h2>
          <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-600">{caseItem.description ?? "No description provided."}</p>
        </div>
      </section>
    </div>
  );
}
