import { useEffect, useState } from "react";

import { api } from "../../api";
import type {
  CaseAISummary,
  CaseItem,
  DocumentItem,
  RiskLevel,
  TaskItem,
  TimelineEvent,
} from "../../types";
import { getLatestApprovedManagementSummary } from "../../services/ai";
import { cleanAIText } from "../../utils/aiText";
import { RiskBadge, StatusBadge } from "./Badges";
import { formatDateTime } from "./formatters";

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

const riskLabels: Record<RiskLevel, string> = {
  Low: "niedrig",
  Medium: "mittel",
  High: "hoch",
};

function getRiskLabel(
  risk: RiskLevel | null | undefined,
): string {
  if (!risk) {
    return "nicht verfügbar";
  }

  return riskLabels[risk];
}

/**
 * Split German management prose without treating common abbreviations such as
 * "z. B." or "d. h." as sentence boundaries.
 */
function splitOverviewSentences(value: string): string[] {
  const abbreviations: Array<[RegExp, string]> = [
    [/\bz\.\s*B\./gi, "z<DOT> B<DOT>"],
    [/\bd\.\s*h\./gi, "d<DOT> h<DOT>"],
    [/\bu\.\s*a\./gi, "u<DOT> a<DOT>"],
    [/\bu\.\s*U\./g, "u<DOT> U<DOT>"],
    [/\bggf\./gi, "ggf<DOT>"],
    [/\bbzw\./gi, "bzw<DOT>"],
    [/\bca\./gi, "ca<DOT>"],
    [/\bNr\./g, "Nr<DOT>"],
    [/\bAbs\./g, "Abs<DOT>"],
    [/\bArt\./g, "Art<DOT>"],
    [/\bDr\./g, "Dr<DOT>"],
  ];

  let protectedText = value;

  for (const [pattern, replacement] of abbreviations) {
    protectedText = protectedText.replace(pattern, replacement);
  }

  return protectedText
    .split(/(?<=[.!?])\s+(?=[A-ZÄÖÜ0-9])/)
    .map((sentence) => sentence.replaceAll("<DOT>", ".").trim())
    .filter(Boolean);
}

/**
 * Keep the Overview scannable without cutting a sentence in the middle.
 * The full AI text remains available in the KI-Assistent tab.
 */
function compactOverviewText(
  value: string | null | undefined,
  maxCharacters: number,
): string | null {
  const cleaned = cleanAIText(value);

  if (!cleaned) {
    return null;
  }

  const normalized = cleaned.replace(/\s+/g, " ").trim();

  if (normalized.length <= maxCharacters) {
    return normalized;
  }

  const sentences = splitOverviewSentences(normalized);
  let result = "";

  for (const sentence of sentences) {
    const candidate = `${result} ${sentence}`.trim();

    if (candidate.length > maxCharacters) {
      break;
    }

    result = candidate;
  }

  if (result) {
    return result;
  }

  // If even the first sentence is longer than the preferred Overview limit,
  // show that complete sentence instead of producing a broken fragment such
  // as "(z. B.". Readability is more important than a hard character limit.
  return sentences[0] ?? normalized;
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
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600">
          {detail}
        </p>
      )}
    </div>
  );
}

function WarningItem({
  children,
}: {
  children: React.ReactNode;
}) {
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
  canEdit,
  isManager,
  onEditCase,
  onRiskConfirmed,
}: OverviewTabProps) {
  const [confirmingRisk, setConfirmingRisk] =
    useState(false);

  const [riskError, setRiskError] =
    useState("");

  const [approvedSummary, setApprovedSummary] =
    useState<CaseAISummary | null>(null);

  const today = new Date();

  today.setHours(
    0,
    0,
    0,
    0,
  );

  const deadline =
    caseItem.primary_deadline
      ? new Date(
          `${caseItem.primary_deadline}T00:00:00`,
        )
      : null;

  const deadlineIsOverdue =
    deadline !== null &&
    deadline < today &&
    caseItem.status !== "Completed";

  const warningStatuses = new Set([
    "New",
    "Under Review",
    "In Progress",
    "Critical",
  ]);

  const needsActiveAttention =
    warningStatuses.has(
      caseItem.status,
    );

  const cleanedNextAction =
    cleanAIText(
      caseItem.next_action,
    );

  const overviewNextAction =
    compactOverviewText(
      cleanedNextAction,
      600,
    );

  const missingNextAction =
    needsActiveAttention &&
    !cleanedNextAction;

  const missingOwner =
    needsActiveAttention &&
    !caseItem.responsible_person?.trim();

  const overdueTasks =
    tasks.filter(
      (task) => {
        if (
          task.status === "Completed" ||
          !task.due_date
        ) {
          return false;
        }

        return (
          new Date(
            `${task.due_date}T00:00:00`,
          ) < today
        );
      },
    );

  useEffect(() => {
    let cancelled = false;

    async function loadApprovedSummary() {
      try {
        const approved =
          await getLatestApprovedManagementSummary(
            caseItem.id,
          );

        if (cancelled) {
          return;
        }

        setApprovedSummary(
          approved,
        );
      } catch {
        if (!cancelled) {
          setApprovedSummary(
            null,
          );
        }
      }
    }

    void loadApprovedSummary();

    return () => {
      cancelled = true;
    };
  }, [
    caseItem.id,
    caseItem.updated_at,
  ]);

  const latestEvent =
    [...timeline]
      .filter((event) => {
        const eventType =
          event.event_type
            .trim()
            .toLowerCase();

        return (
          !event.is_future &&
          eventType !==
            "milestone" &&
          eventType !==
            "task deadline"
        );
      })
      .sort(
        (a, b) =>
          new Date(
            b.occurred_at,
          ).getTime() -
          new Date(
            a.occurred_at,
          ).getTime(),
      )[0];

  const confirmedLatestDevelopment =
    cleanAIText(
      approvedSummary
        ?.latest_development,
    ) || null;

  const cleanedManagementSummary =
    cleanAIText(
      caseItem.management_summary,
    );

  const cleanedDescription =
    cleanAIText(
      caseItem.description,
    );

  const cleanedRiskReason =
    cleanAIText(
      caseItem.risk_reason,
    );

  const overviewRiskReason =
    compactOverviewText(
      cleanedRiskReason,
      420,
    );

  const overviewLatestDevelopment =
    compactOverviewText(
      confirmedLatestDevelopment,
      550,
    );

  const cleanedSuggestedRiskReason =
    cleanAIText(
      caseItem.suggested_risk_reason,
    );

  const relevantDocuments =
    [...documents]
      .sort(
        (a, b) =>
          new Date(
            b.uploaded_at,
          ).getTime() -
          new Date(
            a.uploaded_at,
          ).getTime(),
      )
      .slice(
        0,
        3,
      );

  const riskMismatch =
    Boolean(
      caseItem.suggested_risk,
    ) &&
    caseItem.suggested_risk !==
      caseItem.risk;

  async function confirmSuggestedRisk(): Promise<void> {
    try {
      setConfirmingRisk(
        true,
      );

      setRiskError(
        "",
      );

      const response =
        await api.post<CaseItem>(
          `/cases/${caseItem.id}/confirm-risk`,
        );

      onRiskConfirmed(
        response.data,
      );
    } catch (requestError) {
      console.error(
        "Risikoeinschätzung konnte nicht übernommen werden:",
        requestError,
      );

      setRiskError(
        "Die Risikoeinschätzung konnte nicht übernommen werden.",
      );
    } finally {
      setConfirmingRisk(
        false,
      );
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

          {canEdit && (
            <button
              type="button"
              onClick={
                onEditCase
              }
              className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Informationen bearbeiten
            </button>
          )}
        </div>

        <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-700">
          {cleanedManagementSummary ||
            cleanedDescription ||
            "Noch keine Management-Zusammenfassung vorhanden."}
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <ManagementCard
          label="Status"
          value={
            <StatusBadge
              value={
                caseItem.status
              }
            />
          }
        />

        <ManagementCard
          label="Bestätigtes Risiko"
          value={
            <RiskBadge
              value={
                caseItem.risk
              }
            />
          }
          detail={
            overviewRiskReason ||
            "Keine Risikobegründung vorhanden."
          }
        />

        <ManagementCard
          label="Nächste Maßnahme"
          value={
            overviewNextAction ||
            "Nicht definiert"
          }
          warning={
            missingNextAction
          }
        />

        <ManagementCard
          label="Nächste Frist"
          value={
            caseItem.primary_deadline ??
            "Nicht definiert"
          }
          detail={
            deadlineIsOverdue
              ? "Die Frist ist überschritten."
              : undefined
          }
          warning={
            deadlineIsOverdue
          }
        />
      </section>

      {(deadlineIsOverdue ||
        missingNextAction ||
        missingOwner ||
        overdueTasks.length >
          0) && (
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
          <h2 className="text-lg font-semibold text-amber-950">
            Handlungsbedarf
          </h2>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {deadlineIsOverdue && (
              <WarningItem>
                Die Hauptfrist ist
                überschritten.
              </WarningItem>
            )}

            {missingNextAction && (
              <WarningItem>
                Es wurde keine
                nächste Maßnahme
                definiert.
              </WarningItem>
            )}

            {missingOwner && (
              <WarningItem>
                Es wurde keine
                verantwortliche
                Person zugewiesen.
              </WarningItem>
            )}

            {overdueTasks.length >
              0 && (
              <WarningItem>
                {
                  overdueTasks.length
                }{" "}
                offene Aufgabe(n)
                sind überfällig.
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
                Systemvorschlag zur
                Risikobewertung
              </h2>

              <div className="mt-3">
                <RiskBadge
                  value={
                    caseItem.suggested_risk
                  }
                />
              </div>

              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-blue-900">
                {cleanedSuggestedRiskReason ||
                  "Keine Risikobegründung vorhanden."}
              </p>

              <p className="mt-2 text-xs text-blue-700">
                Der Vorschlag
                verändert das
                bestätigte Risiko
                nicht automatisch.
              </p>

              {riskMismatch &&
                caseItem.suggested_risk && (
                  <div className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-4">
                    <p className="font-semibold text-amber-950">
                      Abweichende
                      Risikobewertung
                    </p>

                    <p className="mt-1 text-sm leading-6 text-amber-900">
                      Das bestätigte
                      Risiko ist{" "}
                      <strong>
                        {getRiskLabel(
                          caseItem.risk,
                        )}
                      </strong>
                      , während das
                      System{" "}
                      <strong>
                        {getRiskLabel(
                          caseItem.suggested_risk,
                        )}
                      </strong>{" "}
                      empfiehlt.
                    </p>

                    <p className="mt-2 text-xs text-amber-800">
                      Bitte prüfen Sie
                      die manuelle
                      Risikobegründung
                      und den
                      Systemvorschlag.
                    </p>
                  </div>
                )}
            </div>

            {isManager &&
              caseItem.suggested_risk !==
                caseItem.risk && (
                <button
                  type="button"
                  onClick={
                    confirmSuggestedRisk
                  }
                  disabled={
                    confirmingRisk
                  }
                  className="rounded-xl bg-blue-950 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {confirmingRisk
                    ? "Wird übernommen..."
                    : "Vorschlag übernehmen"}
                </button>
              )}
          </div>

          {riskError && (
            <p className="mt-4 text-sm font-medium text-red-700">
              {riskError}
            </p>
          )}
        </section>
      )}

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-950">
            Verantwortung und letzte
            Entwicklung
          </h2>

          <dl className="mt-5 space-y-4 text-sm">
            <div>
              <dt className="font-medium text-slate-500">
                Verantwortliche
                Person
              </dt>

              <dd className="mt-1 text-slate-900">
                {caseItem.responsible_person ??
                  "Nicht zugewiesen"}
              </dd>
            </div>

            <div>
              <dt className="font-medium text-slate-500">
                Letzte Entwicklung
              </dt>

              {overviewLatestDevelopment ? (
                <>
                  <dd className="mt-1 whitespace-pre-wrap leading-6 text-slate-900">
                    {
                      overviewLatestDevelopment
                    }
                  </dd>

                  <dd className="mt-2 text-xs text-slate-400">
                    Bestätigte
                    KI-Management-Zusammenfassung
                  </dd>
                </>
              ) : (
                <>
                  <dd className="mt-1 text-slate-900">
                    {latestEvent
                      ? latestEvent.title
                      : "Kein bestätigter Verlaufseintrag vorhanden"}
                  </dd>

                  {latestEvent?.description && (
                    <dd className="mt-2 whitespace-pre-wrap leading-6 text-slate-600">
                      {cleanAIText(
                        latestEvent.description,
                      )}
                    </dd>
                  )}

                  {latestEvent && (
                    <dd className="mt-2 text-xs text-slate-400">
                      {formatDateTime(
                        latestEvent.occurred_at,
                      )}
                    </dd>
                  )}
                </>
              )}
            </div>
          </dl>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-950">
            Relevante Dokumente
          </h2>

          <div className="mt-4 space-y-3">
            {relevantDocuments.length >
            0 ? (
              relevantDocuments.map(
                (document) => (
                  <div
                    key={
                      document.id
                    }
                    className="rounded-xl border border-slate-200 p-3"
                  >
                    <p className="text-sm font-medium text-slate-900">
                      {
                        document.file_name
                      }
                    </p>

                    <p className="mt-1 text-xs text-slate-400">
                      {formatDateTime(
                        document.uploaded_at,
                      )}
                    </p>
                  </div>
                ),
              )
            ) : (
              <p className="text-sm text-slate-500">
                Keine Dokumente
                vorhanden.
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-950">
          Falldetails
        </h2>

        <dl className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Kategorie
            </dt>

            <dd className="mt-2 text-sm text-slate-800">
              {
                caseItem.category
              }
            </dd>
          </div>

          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Unternehmen
            </dt>

            <dd className="mt-2 text-sm text-slate-800">
              {
                caseItem.company
              }
            </dd>
          </div>

          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Abteilung
            </dt>

            <dd className="mt-2 text-sm text-slate-800">
              {caseItem.department ??
                "Nicht angegeben"}
            </dd>
          </div>

          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Externer Kontakt
            </dt>

            <dd className="mt-2 text-sm text-slate-800">
              {caseItem.external_contact ??
                "Nicht angegeben"}
            </dd>
          </div>

          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Nächste Prüfung am
            </dt>

            <dd className="mt-2 text-sm text-slate-800">
              {caseItem.follow_up_date ??
                "Nicht definiert"}
            </dd>
          </div>

          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Finanzieller Betrag
            </dt>

            <dd className="mt-2 text-sm text-slate-800">
              {caseItem.financial_amount !=
              null
                ? `${caseItem.financial_amount.toLocaleString(
                    "de-DE",
                    {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    },
                  )} EUR`
                : "Nicht angegeben"}
            </dd>
          </div>

          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Zuletzt aktualisiert
            </dt>

            <dd className="mt-2 text-sm text-slate-800">
              {formatDateTime(
                caseItem.updated_at,
              )}
            </dd>
          </div>
        </dl>

        <div className="mt-6 border-t border-slate-100 pt-6">
          <h3 className="text-sm font-semibold text-slate-950">
            Beschreibung
          </h3>

          <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">
            {cleanedDescription ||
              "Keine Beschreibung vorhanden."}
          </p>
        </div>
      </section>
    </div>
  );
}