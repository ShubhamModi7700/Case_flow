import { useEffect, useMemo, useState } from "react";
import AssistantMarkdown from "./AssistantMarkdown";

import {
  queryCaseAssistant,
  getCaseChat, sendCaseChat, clearCaseChat, type ChatMessage,
  getCaseAssistantWorkStatus,
  getCaseAssistantIntelligence,
  type AssistantBriefContext,
  type AssistantBriefEvidencePackage,
  type AssistantBriefOutline,
  type AssistantBriefDraft,
  type AssistantBriefReview,
  type AssistantCaseWorkStatus,
  type AssistantCaseIntelligenceResponse,
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
  const uniqueIds = [...new Set(sourceIds)];
  if (uniqueIds.length === 0) return null;
  return (
    <details className="mt-2 text-xs text-slate-600">
      <summary className="w-fit cursor-pointer select-none rounded-md px-1 py-1 font-medium text-slate-600 hover:bg-slate-100">
        Belege anzeigen ({uniqueIds.length})
      </summary>
      <div className="mt-2 flex flex-wrap gap-2">
        {uniqueIds.map((sourceId) => {
          const source = sourcesById.get(sourceId);
          return (
            <span key={sourceId} className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700">
              [{sourceId}] {source?.filename ?? "Quelle nicht zugeordnet"}
              {source && sourceLocation(source) ? ` · ${sourceLocation(source)}` : ""}
            </span>
          );
        })}
      </div>
    </details>
  );
}

function SourcesDisclosure({ sources }: { sources: AssistantSource[] }) {
  if (sources.length === 0) return null;
  return (
    <details className="rounded-lg border border-slate-200 bg-white">
      <summary className="cursor-pointer select-none px-4 py-3 text-sm font-semibold text-slate-700">
        Quellen anzeigen ({sources.length})
      </summary>
      <div className="grid gap-2 border-t border-slate-100 p-3 md:grid-cols-2">
        {sources.map((source) => (
          <div key={source.source_id} className="rounded-lg bg-slate-50 p-3 text-sm">
            <div className="font-semibold text-slate-900">[{source.source_id}] {source.filename}</div>
            {source.document_date && <div className="mt-1 text-xs text-slate-600">Datum: {source.document_date}</div>}
            {source.sender && <div className="text-xs text-slate-600">Absender: {source.sender}</div>}
            {source.is_attachment && source.parent_filename && <div className="text-xs text-slate-600">Anhang aus: {source.parent_filename}</div>}
            {sourceLocation(source) && <div className="text-xs text-slate-600">{sourceLocation(source)}</div>}
          </div>
        ))}
      </div>
    </details>
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
          className="rounded-lg border border-slate-200 bg-white p-4"
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


// Tabular presentation is deliberately limited to the Fallbericht; dedicated analysis views stay intact.
function ReportTable({ headers, rows }: { headers: string[]; rows: React.ReactNode[][] }) {
  return <div className="overflow-x-auto rounded-lg border border-slate-200">
    <table className="w-full min-w-[640px] border-collapse text-left text-sm">
      <thead className="bg-slate-100 text-slate-700"><tr>{headers.map((heading) => <th key={heading} scope="col" className="border-b border-slate-200 px-3 py-2 font-semibold">{heading}</th>)}</tr></thead>
      <tbody className="divide-y divide-slate-100">{rows.map((cells, index) => <tr key={index} className="align-top even:bg-slate-50/50">{cells.map((cell, column) => <td key={column} className="px-3 py-3 leading-6 text-slate-800">{cell}</td>)}</tr>)}</tbody>
    </table>
  </div>;
}

const financeGroups = [
  { key: "invoice", label: "Rechnungen und Forderungen" },
  { key: "recurring", label: "Wiederkehrende Entgelte" },
  { key: "cost", label: "Weitere Kosten" },
  { key: "offer", label: "Angebote und Alternativen" },
  { key: "credit", label: "Gutschriften" },
  { key: "payment", label: "Nachgewiesene Zahlungen" },
  { key: "other", label: "Sonstige / nicht eindeutig zugeordnet" },
] as const;

function deadlineSortKey(value: string | null): string {
  if (!value) return "9999-12-31";
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (iso) return value.trim();
  const german = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(value.trim());
  if (german) return `${german[3]}-${german[2].padStart(2, "0")}-${german[1].padStart(2, "0")}`;
  return "9999-12-31";
}

function ReportChronologyTable({ items, sourcesById }: { items: AssistantChronologyEvent[]; sourcesById: Map<string, AssistantSource> }) {
  return <ReportTable headers={["Datum", "Ereignis", "Bedeutung", "Nachweise"]} rows={items.map((item) => [item.date || "Datum nicht belegt", item.event, item.significance || "Nicht gesondert bewertet", <SourceBadges sourceIds={item.source_ids} sourcesById={sourcesById} />])} />;
}

function ReportEvidenceTable({ items, sourcesById }: { items: AssistantEvidenceLink[]; sourcesById: Map<string, AssistantSource> }) {
  const labels = { direct: "Direkt belegt", indirect: "Indirekt gestützt", contradicted: "Widersprüchlich", insufficient: "Nicht ausreichend belegt" };
  return <ReportTable headers={["Behauptung", "Beweiswert", "Einschränkungen / offene Nachweise", "Quellen"]} rows={items.map((item) => [
    item.claim,
    <><strong>{labels[item.evidence_status ?? "insufficient"]}</strong>{item.evidence_reason && <p className="mt-1">{item.evidence_reason}</p>}</>,
    <>{item.limitations?.map((v, i) => <p key={`l${i}`}>{v}</p>)}{item.missing_proof?.map((v, i) => <p key={`m${i}`}>Fehlt: {v}</p>)}{!item.limitations?.length && !item.missing_proof?.length ? "—" : null}</>,
    <SourceBadges sourceIds={item.source_ids} sourcesById={sourcesById} />,
  ])} />;
}

function ReportEntitiesTable({ items, sourcesById }: { items: AssistantEntity[]; sourcesById: Map<string, AssistantSource> }) {
  return <ReportTable headers={["Person / Organisation", "Typ", "Rolle", "Einordnung", "Quellen"]} rows={items.map((item) => [
    item.name, item.entity_type, item.role || "Nicht belegt", item.role_is_explicit ? "Ausdrücklich belegt" : "Nicht ausdrücklich belegt", <SourceBadges sourceIds={item.source_ids} sourcesById={sourcesById} />,
  ])} />;
}

function EvidenceOverview({
  items,
  sourcesById,
}: {
  items: AssistantEvidenceLink[];
  sourcesById: Map<string, AssistantSource>;
}) {
  if (items.length === 0) {
    return <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Keine belastbare Beweismittelzuordnung erstellt. Prüfen Sie die verfügbaren Dokumente und Quellen.</div>;
  }
  const labels = {
    direct: "Direkt belegt",
    indirect: "Indirekt gestützt",
    contradicted: "Widersprüchlich",
    insufficient: "Nicht ausreichend belegt",
  };
  const tones = {
    direct: "bg-emerald-50 text-emerald-800 border-emerald-200",
    indirect: "bg-blue-50 text-blue-800 border-blue-200",
    contradicted: "bg-amber-50 text-amber-800 border-amber-200",
    insufficient: "bg-slate-100 text-slate-700 border-slate-200",
  };
  return (
    <section>
      <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-700">Beweismittelübersicht</h3>
      <p className="mb-3 text-xs text-slate-500">KI-Einschätzung zur konkreten Behauptung, keine abschließende rechtliche Beweiswürdigung. Quellen und Bewertungen fachlich prüfen.</p>
      <div className="space-y-3">
        {items.map((item, index) => {
          const status = item.evidence_status ?? "insufficient";
          const groups = new Map<string, string[]>();
          for (const id of [...new Set(item.source_ids)]) {
            const source = sourcesById.get(id);
            const name = source?.filename ?? "Unbekanntes Dokument";
            groups.set(name, [...(groups.get(name) ?? []), `${id}${source && sourceLocation(source) ? ` · ${sourceLocation(source)}` : ""}`]);
          }
          return (
            <article key={`${item.claim}-${index}`} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Behauptung {index + 1}</p>
                  <p className="mt-1 text-sm font-semibold leading-6 text-slate-900">{item.claim}</p>
                </div>
                <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${tones[status]}`}>{labels[status]}</span>
              </div>
              {item.relevance && <p className="mt-3 text-sm leading-6 text-slate-700"><strong>Relevanz:</strong> {item.relevance}</p>}
              {item.evidence_reason && <p className="mt-2 text-sm leading-6 text-slate-700"><strong>Beweiswert:</strong> {item.evidence_reason}</p>}
              {(item.limitations?.length ?? 0) > 0 && <div className="mt-3 text-sm text-slate-700"><strong>Grenzen der Beweiskraft</strong><ul className="mt-1 list-disc space-y-1 pl-5">{item.limitations?.map((text, i) => <li key={i}>{text}</li>)}</ul></div>}
              {(item.missing_proof?.length ?? 0) > 0 && <div className="mt-3 text-sm text-slate-700"><strong>Offene Nachweise</strong><ul className="mt-1 list-disc space-y-1 pl-5">{item.missing_proof?.map((text, i) => <li key={i}>{text}</li>)}</ul></div>}
              <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50">
                <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-slate-700">Dokumente und Fundstellen anzeigen ({item.source_ids.length})</summary>
                <div className="space-y-2 border-t border-slate-200 p-3">
                  {[...groups.entries()].map(([filename, ids]) => <div key={filename}><p className="text-xs font-semibold text-slate-800">{filename}</p><p className="mt-1 text-xs leading-5 text-slate-600">{ids.map(id => `[${id}]`).join(" · ")}</p></div>)}
                </div>
              </details>
            </article>
          );
        })}
      </div>
    </section>
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
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
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
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-indigo-700">Schritt 2 · Gliederung</div>
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
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <div>
        <span className="rounded bg-amber-100 px-2 py-1 text-xs font-bold text-amber-900">{item.draft_label || "KI-ENTWURF"}</span>
        <div className="mt-2 text-xs font-semibold uppercase tracking-wide text-emerald-700">Schritt 3 · Schriftsatzentwurf</div>
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
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <div>
        <span className="rounded bg-rose-100 px-2 py-1 text-xs font-bold text-rose-900">{item.review_label || "KI-RED-REVIEW"}</span>
        <div className="mt-2 text-xs font-semibold uppercase tracking-wide text-rose-700">Gegenargumente & Risiken</div>
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

function CaseIntelligenceView({ item }: { item: AssistantCaseIntelligenceResponse }) {
  const sourcesById = useMemo(
    () => new Map(item.sources.map((source) => [source.source_id, source])),
    [item.sources],
  );
  const intel = item.intelligence;
  return (
    <div className="space-y-5 rounded-xl border border-slate-200 bg-white p-5">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-cyan-700">Fall-Intelligence</div>
        <h3 className="mt-1 text-lg font-semibold text-slate-900">Konsolidierte Fallübersicht</h3>
        <p className="mt-1 text-xs text-slate-600">Dokumentenbasierte Erkenntnisse sind quellengebunden; Fristen und Aufgaben stammen direkt aus Case Flow.</p>
        {item.freshness && (
          <div className={`mt-3 rounded-lg border p-3 text-sm ${item.freshness.status === "outdated" ? "border-amber-300 bg-amber-50 text-amber-900" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
            <strong>{item.freshness.status === "outdated" ? "Veraltet" : "Aktuell"}</strong>
            {item.freshness.generated_at && <> · erstellt am {new Date(item.freshness.generated_at).toLocaleString("de-DE")}</>}
            {item.freshness.status === "outdated" && <div className="mt-1 text-xs">Dokumente, Falldaten oder Aufgaben haben sich seit der Erstellung geändert. Bitte Fall-Intelligence aktualisieren.</div>}
          </div>
        )}
        {intel.executive_summary.length > 0 && <div className="mt-3"><EvidenceList items={intel.executive_summary} sourcesById={sourcesById} /></div>}
      </div>
      {intel.key_facts.length > 0 && <div><h4 className="mb-2 font-semibold">Wichtigste Kerntatsachen</h4><EvidenceList items={intel.key_facts.slice(0, 5)} sourcesById={sourcesById} /></div>}
      <div className="grid gap-3 md:grid-cols-2">
        {intel.contradictions.length > 0 && <div className="rounded-lg border border-amber-200 bg-amber-50 p-4"><h4 className="font-semibold text-amber-900">Widersprüche ({intel.contradictions.length})</h4><p className="mt-1 text-sm text-amber-800">Wesentliche Punkte, die vor einer Entscheidung geklärt werden sollten.</p></div>}
        {intel.information_gaps.length > 0 && <div className="rounded-lg border border-slate-200 bg-white p-4"><h4 className="font-semibold">Informationslücken ({intel.information_gaps.length})</h4><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">{intel.information_gaps.slice(0, 3).map((x,i)=><li key={`${x}-${i}`}>{x}</li>)}</ul></div>}
      </div>
      {intel.contradictions.length > 0 && <details className="rounded-lg border border-amber-200 bg-white"><summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-amber-900">Widersprüche im Detail</summary><div className="border-t border-amber-100 p-4"><EvidenceList items={intel.contradictions} sourcesById={sourcesById} /></div></details>}
      {(intel.key_events.length > 0 || intel.key_entities.length > 0 || intel.evidence_map.length > 0 || intel.unresolved_issues.length > 0) && <details className="rounded-lg border border-slate-200 bg-white"><summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-slate-700">Weitere Fallanalyse anzeigen</summary><div className="space-y-5 border-t border-slate-100 p-4">{intel.key_events.length > 0 && <ChronologyView items={intel.key_events} sourcesById={sourcesById} />}{intel.key_entities.length > 0 && <EntitiesView items={intel.key_entities} sourcesById={sourcesById} />}{intel.evidence_map.length > 0 && <EvidenceOverview items={intel.evidence_map} sourcesById={sourcesById} />}{intel.unresolved_issues.length > 0 && <div><h4 className="font-semibold">Offene Prüf- und Tatsachenfragen</h4><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">{intel.unresolved_issues.map((x,i)=><li key={`${x}-${i}`}>{x}</li>)}</ul></div>}</div></details>}
      <WorkStatusView item={item.work_status} />
      <SourcesDisclosure sources={item.sources} />
    </div>
  );
}

function WorkStatusView({ item }: { item: AssistantCaseWorkStatus }) {
  const [showAllTasks, setShowAllTasks] = useState(false);

  const sortedOpenTasks = useMemo(
    () =>
      [...item.open_tasks].sort((a, b) => {
        // Overdue tasks first.
        if (a.is_overdue !== b.is_overdue) return a.is_overdue ? -1 : 1;

        // Then tasks with a deadline before tasks without a deadline.
        if (a.due_date && !b.due_date) return -1;
        if (!a.due_date && b.due_date) return 1;

        // Within those groups, show the earliest deadline first.
        if (a.due_date && b.due_date) {
          const byDate = a.due_date.localeCompare(b.due_date);
          if (byDate !== 0) return byDate;
        }

        // Stable, readable fallback for tasks without/equal deadlines.
        return a.title.localeCompare(b.title, "de");
      }),
    [item.open_tasks],
  );

  const visibleOpenTasks = showAllTasks ? sortedOpenTasks : sortedOpenTasks.slice(0, 5);
  const hiddenTaskCount = Math.max(sortedOpenTasks.length - visibleOpenTasks.length, 0);

  return (
    <div className="space-y-4 rounded-xl border-2 border-amber-200 bg-amber-50 p-4">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-amber-700">Fristen & offene Arbeit</div>
        <h3 className="mt-1 text-lg font-semibold text-slate-900">Arbeitsstand aus Case Flow</h3>
        <p className="mt-1 text-xs text-slate-600">Diese Angaben stammen direkt aus der Case-Flow-Datenbank und werden nicht von der KI erfunden.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-lg bg-white p-3"><div className="text-xs uppercase text-slate-500">Hauptfrist</div><div className={`mt-1 font-semibold ${item.primary_deadline_is_overdue ? "text-red-700" : "text-slate-900"}`}>{item.primary_deadline ?? "Keine hinterlegt"}</div>{item.primary_deadline_is_overdue && <div className="mt-1 text-xs text-red-700">Überfällig</div>}</div>
        <div className="rounded-lg bg-white p-3"><div className="text-xs uppercase text-slate-500">Wiedervorlage</div><div className="mt-1 font-semibold text-slate-900">{item.follow_up_date ?? "Keine hinterlegt"}</div></div>
        <div className="rounded-lg bg-white p-3"><div className="text-xs uppercase text-slate-500">Nächste Maßnahme</div><div className="mt-1 text-sm font-semibold text-slate-900">{item.next_action ?? "Keine hinterlegt"}</div></div>
      </div>
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-semibold text-slate-900">Offene Aufgaben ({item.open_tasks.length})</h4>
          {item.open_tasks.length > 5 && (
            <span className="text-xs text-slate-500">Überfällige und frühe Fristen zuerst</span>
          )}
        </div>
        {item.open_tasks.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600">Keine offenen Aufgaben.</p>
        ) : (
          <>
            <div className="mt-2 space-y-2">
              {visibleOpenTasks.map((task) => (
                <div key={task.id} className="rounded-lg bg-white p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-900">{task.title}</span>
                    {task.is_overdue && <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">Überfällig</span>}
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{task.priority}</span>
                  </div>
                  <div className="mt-1 text-xs text-slate-600">Frist: {task.due_date ?? "keine"} · Verantwortlich: {task.responsible_person ?? "nicht zugewiesen"}{task.category ? ` · Kategorie: ${task.category}` : ""}</div>
                  {task.description && <p className="mt-2 text-sm text-slate-700">{task.description}</p>}
                </div>
              ))}
            </div>
            {sortedOpenTasks.length > 5 && (
              <div className="mt-3 flex justify-center">
                <button
                  type="button"
                  onClick={() => setShowAllTasks((current) => !current)}
                  className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-500"
                >
                  {showAllTasks ? "Weniger anzeigen" : `Weitere ${hiddenTaskCount} Aufgaben anzeigen`}
                </button>
              </div>
            )}
          </>
        )}
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
  const question = "";
  const [chatOpen, setChatOpen] = useState(true);
  const [chatText, setChatText] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [chatHistoryLoading, setChatHistoryLoading] = useState(false);
  const [chatReloadKey, setChatReloadKey] = useState(0);
  useEffect(() => {
    let alive = true;
    setChatHistory([]);
    setChatText("");
    setChatError("");
    setChatHistoryLoading(true);
    getCaseChat(caseId)
      .then((rows) => { if (alive) setChatHistory(rows); })
      .catch((error) => { if (alive) setChatError(`Chatverlauf konnte nicht geladen werden: ${errorMessage(error)}`); })
      .finally(() => { if (alive) setChatHistoryLoading(false); });
    return () => { alive = false; };
  }, [caseId, chatReloadKey]);
  async function sendChat(explicitMessage?: string): Promise<void> {
    const message = (explicitMessage ?? chatText).trim();
    if (message.length < 2 || chatLoading || chatHistoryLoading) return;
    setChatLoading(true); setChatError("");
    try {
      await sendCaseChat(caseId, message);
      setChatText("");
      setChatHistory(await getCaseChat(caseId));
    } catch (e) { setChatError(errorMessage(e)); }
    finally { setChatLoading(false); }
  }
  const [result, setResult] = useState<CaseAssistantResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTask, setActiveTask] = useState<AssistantTaskType>("question");
  const [showBriefForm, setShowBriefForm] = useState(false);
  const [workStatus, setWorkStatus] = useState<AssistantCaseWorkStatus | null>(null);
  const [workStatusLoading, setWorkStatusLoading] = useState(false);
  const [intelligence, setIntelligence] = useState<AssistantCaseIntelligenceResponse | null>(null);
  const [intelligenceLoading, setIntelligenceLoading] = useState(false);
  const [briefStep, setBriefStep] = useState<0 | 1 | 2 | 3 | 4>(0);
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

  async function loadIntelligence(forceRefresh = false): Promise<void> {
    if (intelligenceLoading) return;
    try {
      setIntelligenceLoading(true);
      setWorkStatus(null);
      setResult(null);
      setError("");
      const data = await getCaseAssistantIntelligence(caseId, forceRefresh);
      setIntelligence(data);
      setWorkStatus(null);
      setResult(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIntelligenceLoading(false);
    }
  }

  async function loadWorkStatus(): Promise<void> {
    if (workStatusLoading) return;
    try {
      setWorkStatusLoading(true);
      setIntelligence(null);
      setResult(null);
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
  ): Promise<boolean> {
    const trimmed = (explicitQuestion ?? question).trim();
    if (trimmed.length < 2 || loading) return false;

    try {
      setLoading(true);
      setError("");
      setIntelligence(null);
      setWorkStatus(null);
      setResult(null);
      setActiveTask(taskType);
      const response = await queryCaseAssistant(caseId, trimmed, taskType, explicitBriefContext);
      setResult(response);
      return true;
    } catch (requestError) {
      setError(errorMessage(requestError));
      return false;
    } finally {
      setLoading(false);
    }
  }

  function updateBriefContext(patch: Partial<AssistantBriefContext>): void {
    setBriefContext((current) => ({ ...current, ...patch }));
    // A changed assignment invalidates every downstream artifact.
    setBriefStep(0);
    if (activeTask.startsWith("brief_")) setResult(null);
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
    if (await submit("brief_evidence", request, normalized)) setBriefStep(1);
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
    if (briefStep < 1) return;
    if (await submit("brief_outline", request, normalized)) setBriefStep(2);
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
    if (briefStep < 2) return;
    if (await submit("brief_draft", request, normalized)) setBriefStep(3);
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
    if (briefStep < 3) return;
    if (await submit("brief_review", request, normalized)) setBriefStep(4);
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
        <button type="button" onClick={() => { setChatOpen(true); setResult(null); setIntelligence(null); setWorkStatus(null); setShowBriefForm(false); }} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium">KI-Chat</button>
        <button type="button" disabled={loading || intelligenceLoading} onClick={() => { setChatOpen(false); void submit("report", "Erstelle einen umfassenden belegten Fallbericht mit Kurzüberblick, Chronologie, Beteiligten, Finanzen, Risiken und offenen Punkten."); }} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium">Fallbericht erstellen</button>
        <button
          type="button"
          disabled={loading || intelligenceLoading || workStatusLoading}
          onClick={() => { setChatOpen(false); setShowBriefForm(false); void loadIntelligence(intelligence?.freshness?.status === "outdated"); }}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-500 disabled:opacity-50"
        >
          {intelligenceLoading
            ? "Fall-Intelligence wird erstellt..."
            : intelligence?.freshness?.status === "outdated"
              ? "Fall-Intelligence aktualisieren"
              : "Fall-Intelligence"}
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => { setChatOpen(false); setShowBriefForm((value) => !value); }}
          className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
            showBriefForm ? "border-violet-700 bg-violet-700 text-white" : "border-slate-300 bg-white text-slate-700 hover:border-slate-500"
          }`}
        >
          Schriftsatz vorbereiten
        </button>
      </div>

      {chatOpen && (
        <section aria-label="KI-Chat" className="mb-4 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3 sm:px-5">
            <div>
              <h3 className="font-semibold text-slate-900">KI-Chat</h3>
            </div>
            <button type="button" disabled={chatLoading || chatHistoryLoading || chatHistory.length === 0} className="text-xs text-slate-600 underline disabled:opacity-40" onClick={async () => {
              if (!window.confirm("Eigenen Chatverlauf dieses Falls dauerhaft löschen?")) return;
              try { await clearCaseChat(caseId); setChatHistory([]); setChatError(""); }
              catch (error) { setChatError(errorMessage(error)); }
            }}>Verlauf löschen</button>
          </header>
          <div role="log" aria-label="Chatverlauf" aria-live="polite" className="max-h-[520px] min-h-[190px] space-y-5 overflow-y-auto px-4 py-5 sm:px-6">
            {chatHistoryLoading && <p className="text-sm text-slate-500">Chatverlauf wird geladen...</p>}
            {!chatHistoryLoading && chatHistory.length === 0 && <div className="mx-auto max-w-lg py-4 text-center">
              <div className="text-base font-semibold text-slate-900">Wie kann ich Ihnen helfen?</div>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {["Welche Zahlungen sind noch ungeklärt?", "Welche Nachweise fehlen?"].map((suggestion) => (
                  <button key={suggestion} type="button" disabled={chatLoading} onClick={() => void sendChat(suggestion)} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50">{suggestion}</button>
                ))}
              </div>
            </div>}
            {chatHistory.map((turn) => (
              <div key={turn.id} className={`flex ${turn.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[92%] rounded-2xl px-4 py-3 text-sm sm:max-w-[85%] ${turn.role === "user" ? "bg-slate-100 text-slate-900" : "border border-slate-100 bg-white text-slate-800"}`}>
                  <div className="mb-2 text-xs font-semibold text-slate-500">{turn.role === "user" ? "Sie" : "Case Flow"}</div>
                  <AssistantMarkdown content={turn.content} />
                  {turn.response && turn.response.sources.length > 0 && <details className="mt-3 border-t border-slate-100 pt-2 text-xs text-slate-600">
                    <summary className="cursor-pointer font-medium">Dokumentquellen ({turn.response.sources.length})</summary>
                    <ul className="mt-2 space-y-1">{turn.response.sources.map((source) => <li key={source.source_id}>[{source.source_id}] {source.filename}{source.page_number ? ` · Seite ${source.page_number}` : ""}</li>)}</ul>
                  </details>}
                </div>
              </div>
            ))}
            {chatLoading && <p role="status" className="text-sm text-slate-500">Case Flow erstellt eine Antwort...</p>}
          </div>
          {chatError && <div role="alert" className="mx-4 mb-3 flex flex-wrap items-center gap-3 rounded-lg bg-red-50 p-3 text-sm text-red-700 sm:mx-5">
            <span>{chatError}</span>
            <button type="button" className="font-semibold underline" onClick={() => setChatReloadKey((value) => value + 1)}>Verlauf erneut laden</button>
          </div>}
          <form className="border-t border-slate-100 p-3 sm:p-4" onSubmit={(event) => { event.preventDefault(); void sendChat(); }}>
            <label htmlFor="case-chat-message" className="sr-only">Nachricht an Case Flow</label>
            <textarea id="case-chat-message" rows={2} className="w-full resize-y rounded-xl border border-slate-300 p-3 text-sm outline-none focus:border-slate-500" value={chatText} onChange={(event) => setChatText(event.target.value)} onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void sendChat(); }
            }} placeholder="Fragen Sie etwas zu diesem Fall oder stellen Sie eine Folgefrage..." disabled={chatLoading || chatHistoryLoading} />
            <div className="mt-2 flex items-center justify-between gap-3">
              <span className="text-xs text-slate-500">Nur freigegebene Falldokumente · Enter senden · Shift+Enter Zeilenumbruch</span>
              <button type="submit" disabled={chatLoading || chatHistoryLoading || chatText.trim().length < 2} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">{chatLoading ? "Antwort läuft..." : "Senden ↑"}</button>
            </div>
          </form>
        </section>
      )}
      {showBriefForm && (
        <div className="mb-4 rounded-xl border border-violet-200 bg-white p-4">
          <div className="mb-3">
            <h3 className="font-semibold text-slate-900">Auftrag für die Schriftsatzvorbereitung</h3>
            <p className="mt-1 text-xs text-slate-600">Beweispaket, Gliederung, KI-Entwurf und kritische Gegenprüfung verwenden denselben aufgabenbezogenen Kontext.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">Mandant / Partei *
            <input className="rounded-lg border border-slate-300 p-2.5 text-sm" placeholder="Mandant / Partei *" value={briefContext.client} onChange={(e) => updateBriefContext({ client: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">Rolle
            <input className="rounded-lg border border-slate-300 p-2.5 text-sm" placeholder="Rolle, z. B. Antragstellerin" value={briefContext.role ?? ""} onChange={(e) => updateBriefContext({ role: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">Adressat
            <input className="rounded-lg border border-slate-300 p-2.5 text-sm" placeholder="Adressat, z. B. Amtsgericht Wolfsburg" value={briefContext.recipient ?? ""} onChange={(e) => updateBriefContext({ recipient: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">Dokumentart
            <input className="rounded-lg border border-slate-300 p-2.5 text-sm" placeholder="Dokumentart" value={briefContext.document_type} onChange={(e) => updateBriefContext({ document_type: e.target.value })} />
            </label>
          </div>
          <label className="mt-3 block text-xs font-semibold text-slate-600">Ziel des Schreibens / konkrete Aufgabe *
          <textarea className="mt-3 w-full rounded-lg border border-slate-300 p-2.5 text-sm" rows={3} placeholder="Ziel des Schriftsatzes / konkrete Aufgabe *" value={briefContext.objective} onChange={(e) => updateBriefContext({ objective: e.target.value })} />
          </label>
          <label className="mt-3 block text-xs font-semibold text-slate-600">Zusätzliche Hinweise (optional)
          <textarea className="mt-3 w-full rounded-lg border border-slate-300 p-2.5 text-sm" rows={2} placeholder="Zusätzliche Hinweise (optional)" value={briefContext.additional_instructions ?? ""} onChange={(e) => updateBriefContext({ additional_instructions: e.target.value })} />
          </label>
          <div className="mt-4 grid gap-2 md:grid-cols-4">
            {[
              [1, "Beweispaket", "Fakten & Belege"],
              [2, "Gliederung", "Struktur"],
              [3, "KI-Entwurf", "Entwurf"],
              [4, "Prüfung", "Risiken & Gegenargumente"],
            ].map(([step, title, subtitle]) => {
              const stepNumber = Number(step);
              const completed = briefStep >= stepNumber;
              const current = briefStep + 1 === stepNumber;
              return (
                <div key={stepNumber} className={`rounded-lg border p-3 ${completed ? "border-emerald-200 bg-emerald-50" : current ? "border-violet-300 bg-violet-50" : "border-slate-200 bg-slate-50"}`}>
                  <div className="flex items-center gap-2">
                    <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${completed ? "bg-emerald-700 text-white" : current ? "bg-violet-700 text-white" : "bg-slate-200 text-slate-500"}`}>{completed ? "✓" : stepNumber}</span>
                    <span className="text-sm font-semibold text-slate-900">{title}</span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{completed ? "Erstellt" : current ? "Bereit" : subtitle}</p>
                </div>
              );
            })}
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4">
            <p className="text-sm text-slate-600">{briefStep === 0 ? "Als Nächstes: Belege zusammenstellen" : briefStep === 1 ? "Als Nächstes: Gliederung erstellen" : briefStep === 2 ? "Als Nächstes: Entwurf formulieren" : briefStep === 3 ? "Als Nächstes: Gegenprüfung" : "Alle vier Schritte abgeschlossen"}</p>
            {briefStep === 0 && <button type="button" onClick={() => void submitBriefEvidence()} disabled={loading || !briefContext.client.trim() || briefContext.objective.trim().length < 2} className="rounded-lg bg-violet-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">{loading && activeTask === "brief_evidence" ? "Beweispaket wird erstellt..." : "Beweispaket erstellen →"}</button>}
            {briefStep === 1 && <button type="button" onClick={() => void submitBriefOutline()} disabled={loading} className="rounded-lg bg-violet-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">{loading && activeTask === "brief_outline" ? "Gliederung wird erstellt..." : "Gliederung erstellen →"}</button>}
            {briefStep === 2 && <button type="button" onClick={() => void submitBriefDraft()} disabled={loading} className="rounded-lg bg-violet-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">{loading && activeTask === "brief_draft" ? "Entwurf wird erstellt..." : "KI-Entwurf erstellen →"}</button>}
            {briefStep === 3 && <button type="button" onClick={() => void submitBriefReview()} disabled={loading} className="rounded-lg bg-violet-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">{loading && activeTask === "brief_review" ? "Prüfung wird erstellt..." : "Gegenargumente & Risiken prüfen →"}</button>}
            {briefStep === 4 && <button type="button" onClick={() => void submitBriefEvidence()} disabled={loading || !briefContext.client.trim() || briefContext.objective.trim().length < 2} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-40">Workflow neu starten</button>}
          </div>
          <p className="mt-2 text-xs text-slate-500">Die Schritte werden nacheinander freigeschaltet. Wenn Sie den Auftrag oben ändern, wird der Workflow zurückgesetzt, damit keine Ergebnisse aus einem alten Kontext weiterverwendet werden.</p>
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {intelligence && (
        <div className="mt-6">
          <CaseIntelligenceView item={intelligence} />
        </div>
      )}

      {workStatus && (
        <div className="mt-6">
          <WorkStatusView item={workStatus} />
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-5">
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

          {result.task_type === "report" && <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5">
            <div><h4 className="font-semibold">1. Kurzüberblick</h4><div className="mt-2"><AssistantMarkdown content={result.answer || "Keine belegten Angaben gefunden."} /></div></div>
            <div><h4 className="mb-2 font-semibold">2. Chronologie</h4>{result.chronology.length ? <ReportChronologyTable items={result.chronology} sourcesById={sourcesById} /> : <p className="text-sm text-slate-500">Keine belegten Ereignisse gefunden.</p>}</div>
            <div><h4 className="mb-2 font-semibold">3. Beweismittel und Beweiswert</h4>{result.evidence.length ? <ReportEvidenceTable items={result.evidence} sourcesById={sourcesById} /> : <p className="text-sm text-slate-500">Keine belegten Angaben gefunden.</p>}</div>
            <div><h4 className="mb-2 font-semibold">4. Personen & Rollen</h4>{result.entities.length ? <ReportEntitiesTable items={result.entities} sourcesById={sourcesById} /> : <p className="text-sm text-slate-500">Keine belegten Rollen gefunden.</p>}</div>
            <div><h4 className="mb-2 font-semibold">5. Finanzielle Übersicht</h4>
              {result.report_finances?.length ? <div className="space-y-4">{financeGroups.map((group) => {
                const entries = result.report_finances.filter((item) => (item.category || "other") === group.key);
                return entries.length ? <div key={group.key}><h5 className="mb-2 text-sm font-semibold text-slate-700">{group.label} ({entries.length})</h5><ReportTable headers={["Position", "Betrag", "Dokumentierter Status", "Bedeutung", "Nachweise"]} rows={entries.map((item) => [item.position, item.amount || "Nicht belegt", item.status || "Nicht belegt", item.significance || "—", <SourceBadges sourceIds={item.source_ids} sourcesById={sourcesById} />])} /></div> : null;
              })}</div> : <p className="text-sm text-slate-500">Keine belegten Finanzpositionen gefunden.</p>}
              <p className="mt-2 text-xs text-slate-500">Rechnungen belegen keine Zahlung. Beträge dürfen ohne Prüfung von Gutschriften und Überschneidungen nicht addiert werden.</p>
            </div>
            <div><h4 className="mb-2 font-semibold">6. Fristen & Aufgaben</h4>
              <h5 className="mb-1 text-sm font-medium">Dokumentierte Fristen und Termine</h5>
              {result.report_deadlines?.length ? <ReportTable headers={["Datum", "Frist / Termin", "Art", "Status / Begründung", "Nachweise"]} rows={[...result.report_deadlines].sort((a, b) => deadlineSortKey(a.date).localeCompare(deadlineSortKey(b.date))).map((item) => [item.date || "Datum nicht belegt", item.description, ({ deadline: "Frist", invoice_date: "Rechnungsdatum", offer_expiry: "Angebotsfrist", event_date: "Ereignisdatum", other: "Nicht eindeutig" } as const)[item.date_type || "other"], <><strong>{({ active: "Aktiv", completed: "Erledigt", historical: "Historisch / ersetzt", unclear: "Ungeklärt" } as const)[item.status || "unclear"]}</strong>{item.status_reason && <p className="mt-1">{item.status_reason}</p>}</>, <SourceBadges sourceIds={item.source_ids} sourcesById={sourcesById} />])} /> : <p className="text-sm text-slate-500">Keine belegten Fristen gefunden.</p>}
              <h5 className="mb-1 mt-3 text-sm font-medium">Dokumentierte Aufgaben und Vereinbarungen</h5>
              {result.report_tasks?.length ? <ReportTable headers={["Aufgabe", "Zuständigkeit", "Fällig", "Nachweise"]} rows={result.report_tasks.map((item) => [item.description, item.responsible_person || "Nicht belegt", item.due_date || "Nicht belegt", <SourceBadges sourceIds={item.source_ids} sourcesById={sourcesById} />])} /> : <p className="text-sm text-slate-500">Keine belegten Aufgaben gefunden.</p>}
              <p className="mt-2 text-xs text-slate-500">Dieser Abschnitt zeigt dokumentierte Angaben, nicht automatisch die aktuellen Aufgaben aus der Fall-Datenbank.</p>
              <button type="button" disabled={workStatusLoading} onClick={() => { void loadWorkStatus(); }} className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-slate-500 disabled:opacity-50">{workStatusLoading ? "Arbeitsstand wird geladen..." : "Aktuelle Fristen & Aufgaben aus Case Flow anzeigen"}</button>
            </div>
            <div><h4 className="mb-2 font-semibold">7. Widersprüche</h4>{result.contradictions.length ? <EvidenceList items={result.contradictions} sourcesById={sourcesById} /> : <p className="text-sm text-slate-500">Keine belegten Widersprüche identifiziert.</p>}</div>
            <div><h4 className="mb-2 font-semibold">8. Offene Fragen und fehlende Nachweise</h4>{result.missing_information.length ? <ul className="list-disc space-y-1 pl-5 text-sm">{result.missing_information.map((item, i) => <li key={i}>{item}</li>)}</ul> : <p className="text-sm text-slate-500">Keine weiteren offenen Punkte identifiziert.</p>}</div>
          </section>}
          {result.task_type === "chronology" && <ChronologyView items={result.chronology} sourcesById={sourcesById} />}
          {result.task_type === "evidence" && <EvidenceOverview items={result.evidence} sourcesById={sourcesById} />}
          {result.task_type === "entities" && <EntitiesView items={result.entities} sourcesById={sourcesById} />}

          {result.task_type === "question" && result.answer?.trim() && (
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900">Antwort auf Ihre Frage</h3>
              <div className="mt-3"><AssistantMarkdown content={result.answer} /></div>
            </section>
          )}

          {result.task_type === "question" && result.claims.length > 0 && (
            <details className="rounded-xl border border-slate-200 bg-white">
              <summary className="cursor-pointer select-none px-4 py-3 text-sm font-semibold text-slate-700">
                Belegte Aussagen und Einzelnachweise anzeigen ({result.claims.length})
              </summary>
              <div className="border-t border-slate-100 p-4">
                <EvidenceList items={result.claims} sourcesById={sourcesById} />
              </div>
            </details>
          )}

          {result.task_type !== "question" && result.task_type !== "report" && result.answer?.trim() && (
            <details className="rounded-xl border border-slate-200 bg-white">
              <summary className="cursor-pointer select-none px-4 py-3 text-sm font-medium text-slate-700">
                Zusätzliche KI-Erläuterung anzeigen
              </summary>
              <div className="border-t border-slate-100 px-4 py-3"><AssistantMarkdown content={result.answer} /></div>
            </details>
          )}

          <SourcesDisclosure sources={result.sources} />

          {result.task_type !== "report" && result.contradictions.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
              <h3 className="mb-2 text-sm font-semibold text-amber-900">Widersprüche</h3>
              <EvidenceList items={result.contradictions} sourcesById={sourcesById} />
            </div>
          )}

          {result.task_type !== "report" && result.missing_information.length > 0 && (
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