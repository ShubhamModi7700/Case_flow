import { useMemo, useState } from "react";

import {
  queryCaseAssistant,
  type AssistantChronologyEvent,
  type AssistantEntity,
  type AssistantEvidenceLink,
  type AssistantEvidenceStatement,
  type AssistantSource,
  type AssistantTaskType,
  type CaseAssistantResponse,
} from "../../../services/ai";

type Props = {
  caseId: number;
};

const QUICK_ACTIONS: Array<{
  type: AssistantTaskType;
  label: string;
  question: string;
}> = [
  {
    type: "chronology",
    label: "Chronologie",
    question: "Erstelle eine Chronologie der wichtigsten belegten Ereignisse in diesem Vorgang.",
  },
  {
    type: "evidence",
    label: "Beweismittel",
    question: "Welche wesentlichen Behauptungen sind durch welche Dokumente und Dokumentstellen belegt?",
  },
  {
    type: "entities",
    label: "Personen & Rollen",
    question: "Welche Personen, Unternehmen und Organisationen kommen vor und welche Rollen sind ausdrücklich belegt?",
  },
];

function errorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "response" in error) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response;
    if (typeof response?.data?.detail === "string") {
      return response.data.detail;
    }
  }
  return "Die Anfrage an den KI-Assistenten konnte nicht verarbeitet werden.";
}

function sourceLocation(source: AssistantSource): string {
  const parts: string[] = [];
  if (source.page_number !== null) parts.push(`Seite ${source.page_number}`);
  if (source.sheet_name) parts.push(`Blatt ${source.sheet_name}`);
  if (source.email_section) parts.push(`Abschnitt ${source.email_section}`);
  return parts.join(" · ");
}

function SourceBadges({
  sourceIds,
  sourcesById,
}: {
  sourceIds: string[];
  sourcesById: Map<string, AssistantSource>;
}) {
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {sourceIds.map((sourceId) => {
        const source = sourcesById.get(sourceId);
        return (
          <span
            key={sourceId}
            className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600"
          >
            [{sourceId}] {source?.filename ?? "Quelle"}
          </span>
        );
      })}
    </div>
  );
}

function EvidenceList({
  items,
  sourcesById,
}: {
  items: AssistantEvidenceStatement[];
  sourcesById: Map<string, AssistantSource>;
}) {
  if (items.length === 0) return null;
  return (
    <ul className="space-y-3">
      {items.map((item, index) => (
        <li
          key={`${item.text}-${index}`}
          className="rounded-lg border border-slate-200 bg-white p-3"
        >
          <p className="text-sm text-slate-800">{item.text}</p>
          <SourceBadges sourceIds={item.source_ids} sourcesById={sourcesById} />
        </li>
      ))}
    </ul>
  );
}

function ChronologyView({
  items,
  sourcesById,
}: {
  items: AssistantChronologyEvent[];
  sourcesById: Map<string, AssistantSource>;
}) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Chronologie
      </h3>
      <div className="space-y-3 border-l-2 border-slate-200 pl-4">
        {items.map((item, index) => (
          <div key={`${item.date ?? "ohne-datum"}-${item.event}-${index}`} className="relative">
            <span className="absolute -left-[21px] top-2 h-2.5 w-2.5 rounded-full bg-slate-700" />
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {item.date || "Datum nicht eindeutig belegt"}
              </div>
              <p className="mt-1 text-sm text-slate-900">{item.event}</p>
              <SourceBadges sourceIds={item.source_ids} sourcesById={sourcesById} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EvidenceOverview({
  items,
  sourcesById,
}: {
  items: AssistantEvidenceLink[];
  sourcesById: Map<string, AssistantSource>;
}) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Beweismittelübersicht
      </h3>
      <div className="space-y-3">
        {items.map((item, index) => (
          <div key={`${item.claim}-${index}`} className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-sm font-semibold text-slate-900">{item.claim}</p>
            {item.relevance && (
              <p className="mt-1 text-sm leading-6 text-slate-600">{item.relevance}</p>
            )}
            <SourceBadges sourceIds={item.source_ids} sourcesById={sourcesById} />
          </div>
        ))}
      </div>
    </div>
  );
}

function EntitiesView({
  items,
  sourcesById,
}: {
  items: AssistantEntity[];
  sourcesById: Map<string, AssistantSource>;
}) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Personen, Unternehmen & Rollen
      </h3>
      <div className="grid gap-3 md:grid-cols-2">
        {items.map((item, index) => (
          <div key={`${item.name}-${index}`} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-semibold text-slate-900">{item.name}</p>
                <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">{item.entity_type}</p>
              </div>
              {item.role && (
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                    item.role_is_explicit
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {item.role_is_explicit ? "Rolle belegt" : "Rolle nicht ausdrücklich belegt"}
                </span>
              )}
            </div>
            <p className="mt-3 text-sm text-slate-700">
              Rolle: {item.role || "Keine belastbare Rolle aus der Evidenz ableitbar"}
            </p>
            <SourceBadges sourceIds={item.source_ids} sourcesById={sourcesById} />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CaseAssistant({ caseId }: Props) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<CaseAssistantResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTask, setActiveTask] = useState<AssistantTaskType>("question");

  const sourcesById = useMemo(
    () => new Map((result?.sources ?? []).map((source) => [source.source_id, source])),
    [result],
  );

  async function submit(
    taskType: AssistantTaskType = "question",
    explicitQuestion?: string,
  ): Promise<void> {
    const trimmed = (explicitQuestion ?? question).trim();
    if (trimmed.length < 2 || loading) return;

    try {
      setLoading(true);
      setError("");
      setActiveTask(taskType);
      const response = await queryCaseAssistant(caseId, trimmed, taskType);
      setResult(response);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mb-8 rounded-xl border border-slate-200 bg-slate-50 p-5">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-900">KI-Assistent</h2>
        <p className="mt-1 text-sm text-slate-600">
          Fragen Sie Case Flow zu diesem Vorgang oder verwenden Sie eine strukturierte Analyse.
          Alle Ergebnisse werden nur aus den für Sie freigegebenen, indexierten Dokumenten erstellt.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.type}
            type="button"
            disabled={loading}
            onClick={() => void submit(action.type, action.question)}
            className={`rounded-lg border px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
              activeTask === action.type && result?.task_type === action.type
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-300 bg-white text-slate-700 hover:border-slate-500"
            }`}
          >
            {action.label}
          </button>
        ))}
      </div>

      <textarea
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        placeholder="z. B. Welche Buchhaltungsunterlagen wurden bereits übergeben?"
        rows={4}
        className="w-full rounded-lg border border-slate-300 bg-white p-3 text-sm outline-none focus:border-slate-500"
      />
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={() => void submit("question")}
          disabled={loading || question.trim().length < 2}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Analyse wird erstellt..." : "Fragen"}
        </button>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-5">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Antwort</h3>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-900">{result.answer}</p>
          </div>

          <ChronologyView items={result.chronology} sourcesById={sourcesById} />
          <EvidenceOverview items={result.evidence} sourcesById={sourcesById} />
          <EntitiesView items={result.entities} sourcesById={sourcesById} />

          {result.claims.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
                Belegte Aussagen
              </h3>
              <EvidenceList items={result.claims} sourcesById={sourcesById} />
            </div>
          )}

          {result.sources.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Quellen</h3>
              <div className="grid gap-2 md:grid-cols-2">
                {result.sources.map((source) => (
                  <div key={source.source_id} className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
                    <div className="font-semibold text-slate-900">[{source.source_id}] {source.filename}</div>
                    {source.document_date && <div className="mt-1 text-slate-600">Datum: {source.document_date}</div>}
                    {source.sender && <div className="text-slate-600">Absender: {source.sender}</div>}
                    {sourceLocation(source) && <div className="text-slate-600">{sourceLocation(source)}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.contradictions.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
              <h3 className="mb-2 text-sm font-semibold text-amber-900">Widersprüche</h3>
              <EvidenceList items={result.contradictions} sourcesById={sourcesById} />
            </div>
          )}

          {result.missing_information.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-slate-900">Fehlende Informationen</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                {result.missing_information.map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {result.unsupported_statements.length > 0 && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4">
              <h3 className="text-sm font-semibold text-red-900">Nicht belegt</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-red-800">
                {result.unsupported_statements.map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
