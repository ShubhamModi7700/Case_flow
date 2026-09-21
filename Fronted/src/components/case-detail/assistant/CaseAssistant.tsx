import { useMemo, useState } from "react";

import {
  queryCaseAssistant,
  getCaseAssistantWorkStatus,
  type AssistantBriefContext,
  type AssistantBriefEvidencePackage,
  type AssistantBriefOutline,
  type AssistantBriefDraft,
  type AssistantBriefReview,
  type AssistantCaseWorkStatus,
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

function BriefEvidenceView({
  item,
  sourcesById,
}: {
  item: AssistantBriefEvidencePackage;
  sourcesById: Map<string, AssistantSource>;
}) {
  return (
    <div className="space-y-4 rounded-xl border border-violet-200 bg-violet-50 p-4">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-violet-700">Schriftsatzvorbereitung</div>
        <h3 className="mt-1 text-base font-semibold text-slate-900">Aufgabenbezogenes Beweispaket</h3>
        {item.task_summary && <p className="mt-2 text-sm leading-6 text-slate-700">{item.task_summary}</p>}
        <p className="mt-2 text-xs text-slate-600">Noch kein Schriftsatzentwurf. Dieses Paket dient als geprüfte Tatsachen- und Beweisgrundlage.</p>
      </div>

      {item.established_facts.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-slate-900">Maßgebliche belegte Tatsachen</h4>
          <EvidenceList items={item.established_facts} sourcesById={sourcesById} />
        </div>
      )}

      {item.key_evidence.length > 0 && (
        <EvidenceOverview items={item.key_evidence} sourcesById={sourcesById} />
      )}

      {item.relevant_events.length > 0 && (
        <ChronologyView items={item.relevant_events} sourcesById={sourcesById} />
      )}

      {item.relevant_entities.length > 0 && (
        <EntitiesView items={item.relevant_entities} sourcesById={sourcesById} />
      )}

      {item.open_issues.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <h4 className="text-sm font-semibold text-amber-900">Vor einem Entwurf zu klären</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-900">
            {item.open_issues.map((issue, index) => <li key={`${issue}-${index}`}>{issue}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function BriefOutlineView({
  item,
  sourcesById,
}: {
  item: AssistantBriefOutline;
  sourcesById: Map<string, AssistantSource>;
}) {
  return (
    <div className="space-y-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-indigo-700">Step 9 · Gliederung</div>
        <h3 className="mt-1 text-base font-semibold text-slate-900">{item.title}</h3>
        {item.objective && <p className="mt-2 text-sm leading-6 text-slate-700">{item.objective}</p>}
        <p className="mt-2 text-xs text-slate-600">Noch kein ausformulierter Schriftsatz. Tatsachengrundlagen bleiben mit den freigegebenen Quellen verknüpft.</p>
      </div>
      <ol className="space-y-3">
        {item.sections.map((section, index) => (
          <li key={`${section.heading}-${index}`} className="rounded-lg border border-indigo-100 bg-white p-4">
            <h4 className="font-semibold text-slate-900">{index + 1}. {section.heading}</h4>
            {section.purpose && <p className="mt-1 text-sm text-slate-600">{section.purpose}</p>}
            {section.factual_basis.length > 0 && (
              <div className="mt-3">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Tatsachengrundlage</div>
                <EvidenceList items={section.factual_basis} sourcesById={sourcesById} />
              </div>
            )}
            {section.evidence_notes.length > 0 && (
              <div className="mt-3">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Beweismittel</div>
                <EvidenceOverview items={section.evidence_notes} sourcesById={sourcesById} />
              </div>
            )}
          </li>
        ))}
      </ol>
      {item.open_issues.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <h4 className="text-sm font-semibold text-amber-900">Vor dem Ausformulieren zu klären</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-900">{item.open_issues.map((x, i) => <li key={`${x}-${i}`}>{x}</li>)}</ul>
        </div>
      )}
      {item.drafting_notes.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h4 className="text-sm font-semibold text-slate-900">Hinweise für den späteren Entwurf</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">{item.drafting_notes.map((x, i) => <li key={`${x}-${i}`}>{x}</li>)}</ul>
        </div>
      )}
    </div>
  );
}

function BriefDraftView({ item, sourcesById }: { item: AssistantBriefDraft; sourcesById: Map<string, AssistantSource> }) {
  const renderStatements = (items: AssistantEvidenceStatement[]) => (
    <div className="space-y-3">{items.map((statement, index) => (
      <div key={`${statement.text}-${index}`} className="text-sm leading-7 text-slate-800">
        <p className="whitespace-pre-wrap">{statement.text}</p>
        <SourceBadges sourceIds={statement.source_ids} sourcesById={sourcesById} />
      </div>
    ))}</div>
  );
  return (
    <div className="space-y-4 rounded-xl border-2 border-emerald-200 bg-emerald-50 p-4">
      <div>
        <span className="rounded bg-amber-100 px-2 py-1 text-xs font-bold text-amber-900">{item.draft_label || "KI-ENTWURF"}</span>
        <div className="mt-2 text-xs font-semibold uppercase tracking-wide text-emerald-700">Step 10 · Schriftsatzentwurf</div>
        <h3 className="mt-1 text-lg font-semibold text-slate-900">{item.title}</h3>
        <p className="mt-2 text-xs text-slate-600">Nicht freigegebene KI-Fassung. Vor Verwendung fachlich prüfen, bearbeiten und freigeben.</p>
      </div>
      {item.introduction.length > 0 && <div className="rounded-lg bg-white p-4">{renderStatements(item.introduction)}</div>}
      {item.sections.map((section, index) => (
        <div key={`${section.heading}-${index}`} className="rounded-lg border border-emerald-100 bg-white p-4">
          <h4 className="mb-3 font-semibold text-slate-900">{index + 1}. {section.heading}</h4>
          {renderStatements(section.paragraphs)}
        </div>
      ))}
      {item.conclusion.length > 0 && <div className="rounded-lg bg-white p-4"><h4 className="mb-3 font-semibold">Schluss</h4>{renderStatements(item.conclusion)}</div>}
      {item.open_issues.length > 0 && <div className="rounded-lg border border-amber-200 bg-amber-50 p-4"><h4 className="font-semibold text-amber-900">Offene Punkte</h4><ul className="mt-2 list-disc pl-5 text-sm text-amber-900">{item.open_issues.map((x,i)=><li key={`${x}-${i}`}>{x}</li>)}</ul></div>}
      {item.review_notes.length > 0 && <div className="rounded-lg border border-slate-200 bg-white p-4"><h4 className="font-semibold">Prüfhinweise</h4><ul className="mt-2 list-disc pl-5 text-sm text-slate-700">{item.review_notes.map((x,i)=><li key={`${x}-${i}`}>{x}</li>)}</ul></div>}
    </div>
  );
}


function BriefReviewView({ item, sourcesById }: { item: AssistantBriefReview; sourcesById: Map<string, AssistantSource> }) {
  return (
    <div className="space-y-4 rounded-xl border-2 border-rose-200 bg-rose-50 p-4">
      <div>
        <span className="rounded bg-rose-100 px-2 py-1 text-xs font-bold text-rose-900">{item.review_label || "KI-RED-REVIEW"}</span>
        <div className="mt-2 text-xs font-semibold uppercase tracking-wide text-rose-700">Step 11 · Gegenargumente & Risiken</div>
        <h3 className="mt-1 text-lg font-semibold text-slate-900">Kritische Gegenprüfung</h3>
        <p className="mt-2 text-xs text-slate-600">Keine abschließende Rechtsbewertung. Gegenargumente, Risiken und Prüfpunkte müssen fachlich bewertet werden.</p>
      </div>
      {item.counterarguments.length > 0 && <div><h4 className="mb-2 font-semibold">Mögliche Gegenargumente</h4><div className="space-y-3">{item.counterarguments.map((x,i)=><div key={`${x.argument}-${i}`} className="rounded-lg bg-white p-4"><p className="text-sm font-semibold">{x.argument}</p>{x.response_option && <p className="mt-2 text-sm text-slate-700"><strong>Mögliche Reaktion:</strong> {x.response_option}</p>}<SourceBadges sourceIds={x.source_ids} sourcesById={sourcesById}/></div>)}</div></div>}
      {item.factual_risks.length > 0 && <div><h4 className="mb-2 font-semibold">Tatsachen- und Beweisrisiken</h4><div className="space-y-3">{item.factual_risks.map((x,i)=><div key={`${x.risk}-${i}`} className="rounded-lg bg-white p-4"><div className="flex gap-2"><p className="text-sm font-semibold">{x.risk}</p><span className="rounded bg-amber-100 px-2 py-0.5 text-xs">{x.impact}</span></div>{x.mitigation && <p className="mt-2 text-sm text-slate-700"><strong>Gegenmaßnahme:</strong> {x.mitigation}</p>}<SourceBadges sourceIds={x.source_ids} sourcesById={sourcesById}/></div>)}</div></div>}
      {item.contradictions.length > 0 && <div><h4 className="mb-2 font-semibold">Widersprüche</h4><EvidenceList items={item.contradictions} sourcesById={sourcesById}/></div>}
      {item.evidence_gaps.length > 0 && <div className="rounded-lg border border-amber-200 bg-amber-50 p-4"><h4 className="font-semibold text-amber-900">Beweislücken</h4><ul className="mt-2 list-disc pl-5 text-sm text-amber-900">{item.evidence_gaps.map((x,i)=><li key={`${x}-${i}`}>{x}</li>)}</ul></div>}
      {item.legal_review_points.length > 0 && <div className="rounded-lg bg-white p-4"><h4 className="font-semibold">Rechtlich zu prüfen</h4><ul className="mt-2 list-disc pl-5 text-sm text-slate-700">{item.legal_review_points.map((x,i)=><li key={`${x}-${i}`}>{x}</li>)}</ul></div>}
      {item.recommended_checks.length > 0 && <div className="rounded-lg bg-white p-4"><h4 className="font-semibold">Empfohlene Prüfungen vor Freigabe</h4><ul className="mt-2 list-disc pl-5 text-sm text-slate-700">{item.recommended_checks.map((x,i)=><li key={`${x}-${i}`}>{x}</li>)}</ul></div>}
    </div>
  );
}

function WorkStatusView({ item }: { item: AssistantCaseWorkStatus }) {
  return (
    <div className="space-y-4 rounded-xl border-2 border-amber-200 bg-amber-50 p-4">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-amber-700">Step 12 · Fristen & offene Arbeit</div>
        <h3 className="mt-1 text-lg font-semibold text-slate-900">Arbeitsstand aus Case Flow</h3>
        <p className="mt-1 text-xs text-slate-600">Diese Angaben stammen direkt aus der Case-Flow-Datenbank und werden nicht von der KI erfunden.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-lg bg-white p-3"><div className="text-xs uppercase text-slate-500">Hauptfrist</div><div className={`mt-1 font-semibold ${item.primary_deadline_is_overdue ? "text-red-700" : "text-slate-900"}`}>{item.primary_deadline ?? "Keine hinterlegt"}</div>{item.primary_deadline_is_overdue && <div className="mt-1 text-xs text-red-700">Überfällig</div>}</div>
        <div className="rounded-lg bg-white p-3"><div className="text-xs uppercase text-slate-500">Wiedervorlage</div><div className="mt-1 font-semibold text-slate-900">{item.follow_up_date ?? "Keine hinterlegt"}</div></div>
        <div className="rounded-lg bg-white p-3"><div className="text-xs uppercase text-slate-500">Nächste Maßnahme</div><div className="mt-1 text-sm font-semibold text-slate-900">{item.next_action ?? "Keine hinterlegt"}</div></div>
      </div>
      <div>
        <h4 className="font-semibold text-slate-900">Offene Aufgaben ({item.open_tasks.length})</h4>
        {item.open_tasks.length === 0 ? <p className="mt-2 text-sm text-slate-600">Keine offenen Aufgaben.</p> : <div className="mt-2 space-y-2">{item.open_tasks.map((task) => <div key={task.id} className="rounded-lg bg-white p-3"><div className="flex flex-wrap items-center gap-2"><span className="font-semibold text-slate-900">{task.title}</span>{task.is_overdue && <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">Überfällig</span>}<span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{task.priority}</span></div><div className="mt-1 text-xs text-slate-600">Frist: {task.due_date ?? "keine"} · Verantwortlich: {task.responsible_person ?? "nicht zugewiesen"}{task.category ? ` · Kategorie: ${task.category}` : ""}</div>{task.description && <p className="mt-2 text-sm text-slate-700">{task.description}</p>}</div>)}</div>}
      </div>
      <div>
        <h4 className="font-semibold text-slate-900">Offene Entscheidungen ({item.open_decisions.length})</h4>
        {item.open_decisions.length === 0 ? <p className="mt-2 text-sm text-slate-600">Keine ausdrücklich als Entscheidung/Freigabe kategorisierte offene Aufgabe.</p> : <div className="mt-2 space-y-2">{item.open_decisions.map((decision) => <div key={decision.task_id} className="rounded-lg bg-white p-3"><div className="font-semibold text-slate-900">{decision.title}</div><div className="mt-1 text-xs text-slate-600">Frist: {decision.due_date ?? "keine"} · Verantwortlich: {decision.responsible_person ?? "nicht zugewiesen"}</div>{decision.description && <p className="mt-2 text-sm text-slate-700">{decision.description}</p>}</div>)}</div>}
      </div>
      <p className="text-xs text-slate-500">{item.note}</p>
    </div>
  );
}

export default function CaseAssistant({ caseId }: Props) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<CaseAssistantResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTask, setActiveTask] = useState<AssistantTaskType>("question");
  const [showBriefForm, setShowBriefForm] = useState(false);
  const [workStatus, setWorkStatus] = useState<AssistantCaseWorkStatus | null>(null);
  const [workStatusLoading, setWorkStatusLoading] = useState(false);
  const [briefContext, setBriefContext] = useState<AssistantBriefContext>({
    client: "",
    role: null,
    recipient: null,
    document_type: "Schriftsatz",
    objective: "",
    additional_instructions: null,
  });

  const sourcesById = useMemo(
    () => new Map((result?.sources ?? []).map((source) => [source.source_id, source])),
    [result],
  );

  async function loadWorkStatus(): Promise<void> {
    if (workStatusLoading) return;
    try {
      setWorkStatusLoading(true);
      setError("");
      const data = await getCaseAssistantWorkStatus(caseId);
      setWorkStatus(data);
      setResult(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setWorkStatusLoading(false);
    }
  }

  async function submit(
    taskType: AssistantTaskType = "question",
    explicitQuestion?: string,
    explicitBriefContext?: AssistantBriefContext,
  ): Promise<void> {
    const trimmed = (explicitQuestion ?? question).trim();
    if (trimmed.length < 2 || loading) return;

    try {
      setLoading(true);
      setError("");
      setActiveTask(taskType);
      const response = await queryCaseAssistant(caseId, trimmed, taskType, explicitBriefContext);
      setResult(response);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function submitBriefEvidence(): Promise<void> {
    const client = briefContext.client.trim();
    const objective = briefContext.objective.trim();
    if (!client || objective.length < 2 || loading) return;

    const normalized: AssistantBriefContext = {
      client,
      role: briefContext.role?.trim() || null,
      recipient: briefContext.recipient?.trim() || null,
      document_type: briefContext.document_type.trim() || "Schriftsatz",
      objective,
      additional_instructions: briefContext.additional_instructions?.trim() || null,
    };
    const request = `Stelle ein aufgabenbezogenes Beweispaket für die Vorbereitung von ${normalized.document_type} zusammen. Ziel: ${normalized.objective}`;
    await submit("brief_evidence", request, normalized);
  }

  async function submitBriefOutline(): Promise<void> {
    const client = briefContext.client.trim();
    const objective = briefContext.objective.trim();
    if (!client || objective.length < 2 || loading) return;
    const normalized: AssistantBriefContext = {
      client,
      role: briefContext.role?.trim() || null,
      recipient: briefContext.recipient?.trim() || null,
      document_type: briefContext.document_type.trim() || "Schriftsatz",
      objective,
      additional_instructions: briefContext.additional_instructions?.trim() || null,
    };
    const request = `Erstelle eine beleggestützte Gliederung für ${normalized.document_type}. Ziel: ${normalized.objective}`;
    await submit("brief_outline", request, normalized);
  }

  async function submitBriefDraft(): Promise<void> {
    const client = briefContext.client.trim();
    const objective = briefContext.objective.trim();
    if (!client || objective.length < 2 || loading) return;
    const normalized: AssistantBriefContext = {
      client,
      role: briefContext.role?.trim() || null,
      recipient: briefContext.recipient?.trim() || null,
      document_type: briefContext.document_type.trim() || "Schriftsatz",
      objective,
      additional_instructions: briefContext.additional_instructions?.trim() || null,
    };
    const request = `Erstelle einen beleggestützten KI-Entwurf für ${normalized.document_type}. Ziel: ${normalized.objective}`;
    await submit("brief_draft", request, normalized);
  }

  async function submitBriefReview(): Promise<void> {
    const client = briefContext.client.trim();
    const objective = briefContext.objective.trim();
    if (!client || objective.length < 2 || loading) return;
    const normalized: AssistantBriefContext = {
      client,
      role: briefContext.role?.trim() || null,
      recipient: briefContext.recipient?.trim() || null,
      document_type: briefContext.document_type.trim() || "Schriftsatz",
      objective,
      additional_instructions: briefContext.additional_instructions?.trim() || null,
    };
    const request = `Führe eine kritische Gegenprüfung mit Gegenargumenten und Risiken für ${normalized.document_type} durch. Ziel: ${normalized.objective}`;
    await submit("brief_review", request, normalized);
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
        <button
          type="button"
          disabled={loading || workStatusLoading}
          onClick={() => void loadWorkStatus()}
          className="rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm font-medium text-amber-800 transition hover:border-amber-500 disabled:opacity-50"
        >
          {workStatusLoading ? "Arbeitsstand wird geladen..." : "Fristen & Aufgaben"}
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => setShowBriefForm((value) => !value)}
          className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
            showBriefForm ? "border-violet-700 bg-violet-700 text-white" : "border-violet-300 bg-white text-violet-800 hover:border-violet-500"
          }`}
        >
          Schriftsatz vorbereiten
        </button>
      </div>

      {showBriefForm && (
        <div className="mb-4 rounded-xl border border-violet-200 bg-white p-4">
          <div className="mb-3">
            <h3 className="font-semibold text-slate-900">Auftrag für die Schriftsatzvorbereitung</h3>
            <p className="mt-1 text-xs text-slate-600">Beweispaket, Gliederung, KI-Entwurf und kritische Gegenprüfung verwenden denselben aufgabenbezogenen Kontext.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <input className="rounded-lg border border-slate-300 p-2.5 text-sm" placeholder="Mandant / Partei *" value={briefContext.client} onChange={(e) => setBriefContext((v) => ({...v, client: e.target.value}))} />
            <input className="rounded-lg border border-slate-300 p-2.5 text-sm" placeholder="Rolle, z. B. Antragstellerin" value={briefContext.role ?? ""} onChange={(e) => setBriefContext((v) => ({...v, role: e.target.value}))} />
            <input className="rounded-lg border border-slate-300 p-2.5 text-sm" placeholder="Adressat, z. B. Amtsgericht Wolfsburg" value={briefContext.recipient ?? ""} onChange={(e) => setBriefContext((v) => ({...v, recipient: e.target.value}))} />
            <input className="rounded-lg border border-slate-300 p-2.5 text-sm" placeholder="Dokumentart" value={briefContext.document_type} onChange={(e) => setBriefContext((v) => ({...v, document_type: e.target.value}))} />
          </div>
          <textarea className="mt-3 w-full rounded-lg border border-slate-300 p-2.5 text-sm" rows={3} placeholder="Ziel des Schriftsatzes / konkrete Aufgabe *" value={briefContext.objective} onChange={(e) => setBriefContext((v) => ({...v, objective: e.target.value}))} />
          <textarea className="mt-3 w-full rounded-lg border border-slate-300 p-2.5 text-sm" rows={2} placeholder="Zusätzliche Hinweise (optional)" value={briefContext.additional_instructions ?? ""} onChange={(e) => setBriefContext((v) => ({...v, additional_instructions: e.target.value}))} />
          <div className="mt-3 flex justify-end">
            <button type="button" onClick={() => void submitBriefEvidence()} disabled={loading || !briefContext.client.trim() || briefContext.objective.trim().length < 2} className="rounded-lg bg-violet-700 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">
              {loading && activeTask === "brief_evidence" ? "Beweispaket wird erstellt..." : "Beweispaket erstellen"}
            </button>
            <button type="button" onClick={() => void submitBriefOutline()} disabled={loading || !briefContext.client.trim() || briefContext.objective.trim().length < 2} className="ml-2 rounded-lg bg-indigo-700 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">
              {loading && activeTask === "brief_outline" ? "Gliederung wird erstellt..." : "Gliederung erstellen"}
            </button>
            <button type="button" onClick={() => void submitBriefDraft()} disabled={loading || !briefContext.client.trim() || briefContext.objective.trim().length < 2} className="ml-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">
              {loading && activeTask === "brief_draft" ? "Entwurf wird erstellt..." : "KI-Entwurf erstellen"}
            </button>
            <button type="button" onClick={() => void submitBriefReview()} disabled={loading || !briefContext.client.trim() || briefContext.objective.trim().length < 2} className="ml-2 rounded-lg bg-rose-700 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">
              {loading && activeTask === "brief_review" ? "Red Review wird erstellt..." : "Gegenargumente & Risiken"}
            </button>
          </div>
        </div>
      )}

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

      {workStatus && (
        <div className="mt-6">
          <WorkStatusView item={workStatus} />
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-5">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Antwort</h3>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-900">{result.answer}</p>
          </div>

          {result.brief_evidence_package && (
            <BriefEvidenceView item={result.brief_evidence_package} sourcesById={sourcesById} />
          )}

          {result.brief_outline && (
            <BriefOutlineView item={result.brief_outline} sourcesById={sourcesById} />
          )}

          {result.brief_draft && (
            <BriefDraftView item={result.brief_draft} sourcesById={sourcesById} />
          )}

          {result.brief_review && (
            <BriefReviewView item={result.brief_review} sourcesById={sourcesById} />
          )}

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
                    {source.is_attachment && source.parent_filename && (
                      <div className="text-slate-600">Anhang aus: {source.parent_filename}</div>
                    )}
                    {source.is_attachment && source.root_email_filename && source.root_email_filename !== source.parent_filename && (
                      <div className="text-slate-600">Ursprüngliche E-Mail: {source.root_email_filename}</div>
                    )}
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
