import { useState } from "react";

import { api } from "../../api";
import type {
  CaseItem,
  DocumentItem,
  TaskItem,
  TimelineEvent,
} from "../../types";
import { RiskBadge, StatusBadge } from "./Badges";
import { formatDateTime } from "./formatters";

interface OverviewTabProps {
  caseItem: CaseItem;
  tasks: TaskItem[];
  documents: DocumentItem[];
  timeline: TimelineEvent[];
  onEditCase: () => void;
  onRiskConfirmed: (updatedCase: CaseItem) => void;
}

function ManagementCard({
  label,
  value,
  detail,
  warning = false,
}: {
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  warning?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border p-5 shadow-sm ${
        warning
          ? "border-red-200 bg-red-50"
          : "border-slate-200 bg-white"
      }`}
    >
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <div className="mt-3 text-sm font-semibold text-slate-950">
        {value}
      </div>
      {detail && (
        <p className="mt-2 text-sm leading-6 text-slate-600">
          {detail}
        </p>
      )}
    </div>
  );
}

function WarningItem({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-amber-200 bg-white/70 px-4 py-3 text-sm text-amber-950">
      {children}
    </div>
  );
}

export default function OverviewTab({
  caseItem,
  tasks,
  documents,
  timeline,
  onEditCase,
  onRiskConfirmed,
}: OverviewTabProps) {
  const [confirmingRisk, setConfirmingRisk] = useState(false);
  const [riskError, setRiskError] = useState("");

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const deadline = caseItem.primary_deadline
    ? new Date(`${caseItem.primary_deadline}T00:00:00`)
    : null;
  const deadlineIsOverdue =
    deadline !== null &&
    deadline < today &&
    caseItem.status !== "Completed";
  const missingNextAction = !caseItem.next_action?.trim();
  const missingOwner = !caseItem.responsible_person?.trim();
  const overdueTasks = tasks.filter((task) => {
    if (task.status === "Completed" || !task.due_date) return false;
    return new Date(`${task.due_date}T00:00:00`) < today;
  });

  const latestEvent = [...timeline].sort(
    (a, b) =>
      new Date(b.occurred_at).getTime() -
      new Date(a.occurred_at).getTime(),
  )[0];
  const relevantDocuments = [...documents]
    .sort(
      (a, b) =>
        new Date(b.uploaded_at).getTime() -
        new Date(a.uploaded_at).getTime(),
    )
    .slice(0, 3);

  async function confirmSuggestedRisk(): Promise<void> {
    try {
      setConfirmingRisk(true);
      setRiskError("");
      const response = await api.post<CaseItem>(
        `/cases/${caseItem.id}/confirm-risk`,
      );
      onRiskConfirmed(response.data);
    } catch (requestError) {
      console.error("Risikoeinschätzung konnte nicht übernommen werden:", requestError);
      setRiskError("Die Risikoeinschätzung konnte nicht übernommen werden.");
    } finally {
      setConfirmingRisk(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Management-Zusammenfassung
            </p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">
              Aktuelle Situation
            </h2>
          </div>
          <button
            type="button"
            onClick={onEditCase}
            className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Informationen bearbeiten
          </button>
        </div>
        <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-700">
          {caseItem.management_summary ??
            caseItem.description ??
            "Noch keine Management-Zusammenfassung vorhanden."}
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <ManagementCard
          label="Status"
          value={<StatusBadge value={caseItem.status} />}
        />
        <ManagementCard
          label="Bestätigtes Risiko"
          value={<RiskBadge value={caseItem.risk} />}
          detail={caseItem.risk_reason ?? "Keine Risikobegründung vorhanden."}
        />
        <ManagementCard
          label="Nächste Maßnahme"
          value={caseItem.next_action ?? "Nicht definiert"}
          warning={missingNextAction}
        />
        <ManagementCard
          label="Nächste Frist"
          value={caseItem.primary_deadline ?? "Nicht definiert"}
          detail={deadlineIsOverdue ? "Die Frist ist überschritten." : undefined}
          warning={deadlineIsOverdue}
        />
      </section>

      {(deadlineIsOverdue ||
        missingNextAction ||
        missingOwner ||
        overdueTasks.length > 0) && (
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
          <h2 className="text-lg font-semibold text-amber-950">
            Handlungsbedarf
          </h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {deadlineIsOverdue && (
              <WarningItem>Die Hauptfrist ist überschritten.</WarningItem>
            )}
            {missingNextAction && (
              <WarningItem>
                Es wurde keine nächste Maßnahme definiert.
              </WarningItem>
            )}
            {missingOwner && (
              <WarningItem>
                Es wurde keine verantwortliche Person zugewiesen.
              </WarningItem>
            )}
            {overdueTasks.length > 0 && (
              <WarningItem>
                {overdueTasks.length} offene Aufgabe(n) sind überfällig.
              </WarningItem>
            )}
          </div>
        </section>
      )}

      {caseItem.suggested_risk && (
        <section className="rounded-2xl border border-blue-200 bg-blue-50 p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-wider text-blue-600">
                Automatische Empfehlung
              </p>
              <h2 className="mt-2 text-lg font-semibold text-blue-950">
                Systemvorschlag zur Risikobewertung
              </h2>
              <div className="mt-3">
                <RiskBadge value={caseItem.suggested_risk} />
              </div>
              <p className="mt-3 text-sm leading-6 text-blue-900">
                {caseItem.suggested_risk_reason}
              </p>
              <p className="mt-2 text-xs text-blue-700">
                Der Vorschlag verändert das bestätigte Risiko nicht automatisch.
              </p>
            </div>
            {caseItem.suggested_risk !== caseItem.risk && (
              <button
                type="button"
                onClick={confirmSuggestedRisk}
                disabled={confirmingRisk}
                className="rounded-xl bg-blue-950 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {confirmingRisk ? "Wird übernommen..." : "Vorschlag übernehmen"}
              </button>
            )}
          </div>
          {riskError && (
            <p className="mt-4 text-sm font-medium text-red-700">{riskError}</p>
          )}
        </section>
      )}

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-950">
            Verantwortung und letzte Entwicklung
          </h2>
          <dl className="mt-5 space-y-4 text-sm">
            <div>
              <dt className="font-medium text-slate-500">Verantwortliche Person</dt>
              <dd className="mt-1 text-slate-900">
                {caseItem.responsible_person ?? "Nicht zugewiesen"}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-slate-500">Letzte Entwicklung</dt>
              <dd className="mt-1 text-slate-900">
                {latestEvent ? latestEvent.title : "Kein Verlaufseintrag vorhanden"}
              </dd>
              {latestEvent?.description && (
                <dd className="mt-2 text-slate-600">{latestEvent.description}</dd>
              )}
              {latestEvent && (
                <dd className="mt-2 text-xs text-slate-400">
                  {formatDateTime(latestEvent.occurred_at)}
                </dd>
              )}
            </div>
          </dl>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-950">
            Relevante Dokumente
          </h2>
          <div className="mt-4 space-y-3">
            {relevantDocuments.length > 0 ? (
              relevantDocuments.map((document) => (
                <div
                  key={document.id}
                  className="rounded-xl border border-slate-200 p-3"
                >
                  <p className="text-sm font-medium text-slate-900">
                    {document.file_name}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    {formatDateTime(document.uploaded_at)}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">Keine Dokumente vorhanden.</p>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-950">Falldetails</h2>
        <dl className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <div><dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">Kategorie</dt><dd className="mt-2 text-sm text-slate-800">{caseItem.category}</dd></div>
          <div><dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">Unternehmen</dt><dd className="mt-2 text-sm text-slate-800">{caseItem.company}</dd></div>
          <div><dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">Abteilung</dt><dd className="mt-2 text-sm text-slate-800">{caseItem.department ?? "Nicht angegeben"}</dd></div>
          <div><dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">Externer Kontakt</dt><dd className="mt-2 text-sm text-slate-800">{caseItem.external_contact ?? "Nicht angegeben"}</dd></div>
          <div><dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">Wiedervorlage</dt><dd className="mt-2 text-sm text-slate-800">{caseItem.follow_up_date ?? "Nicht definiert"}</dd></div>
          <div><dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">Zuletzt aktualisiert</dt><dd className="mt-2 text-sm text-slate-800">{formatDateTime(caseItem.updated_at)}</dd></div>
        </dl>
        <div className="mt-6 border-t border-slate-100 pt-6">
          <h3 className="text-sm font-semibold text-slate-950">Beschreibung</h3>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">
            {caseItem.description ?? "Keine Beschreibung vorhanden."}
          </p>
        </div>
      </section>
    </div>
  );
}
