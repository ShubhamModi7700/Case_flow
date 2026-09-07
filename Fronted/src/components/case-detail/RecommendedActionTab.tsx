import { useEffect, useMemo, useState } from "react";
import { getManagementSummaries } from "../../services/ai";
import type { CaseAISummary, DocumentItem } from "../../types";
import { cleanAIText } from "../../utils/aiText";

type Props = {
  caseId: number;
  documents: DocumentItem[];
  onOpenAI: () => void;
};

function dateLabel(value: string | null) {
  if (!value) return "Keine klare Frist aus dem Dokument erkennbar";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("de-DE");
}

function isApproved(summary: CaseAISummary) {
  return ["Approved", "EditedAndApproved"].includes(summary.status);
}

export default function RecommendedActionTab({
  caseId,
  documents,
  onOpenAI,
}: Props) {
  const [items, setItems] = useState<CaseAISummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        setLoading(true);
        setError("");
        setItems(await getManagementSummaries(caseId));
      } catch {
        setError("Die Handlungsempfehlung konnte nicht geladen werden.");
      } finally {
        setLoading(false);
      }
    })();
  }, [caseId]);

  // IMPORTANT:
  // This tab is the business-facing result view. Pending AI drafts belong only
  // in "KI-Vorschläge prüfen" and must never be shown here as if confirmed.
  const summary = useMemo(
    () => items.find(isApproved) ?? null,
    [items],
  );

  const hasPendingSummary = useMemo(
    () => items.some((item) => item.status === "Pending"),
    [items],
  );

  const docMap = useMemo(
    () => new Map(documents.map((document) => [document.id, document.file_name])),
    [documents],
  );

  if (loading) {
    return (
      <div className="p-8 text-slate-500">
        Handlungsempfehlung wird geladen...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
        <div className="mx-auto max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            Handlungsempfehlung
          </p>
          <h2 className="mt-2 text-xl font-semibold text-slate-950">
            Noch keine bestätigte Handlungsempfehlung
          </h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            In diesem Bereich werden ausschließlich fachlich geprüfte und
            bestätigte Handlungsempfehlungen angezeigt. KI-Entwürfe werden
            zunächst unter „KI-Vorschläge prüfen“ bearbeitet, bestätigt oder
            abgelehnt.
          </p>

          {hasPendingSummary ? (
            <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-left">
              <p className="font-semibold text-amber-950">
                Ein KI-Vorschlag wartet auf Prüfung
              </p>
              <p className="mt-1 text-sm leading-6 text-amber-900">
                Der Entwurf wird hier bewusst noch nicht angezeigt, damit ein
                ungeprüfter KI-Vorschlag nicht mit einer freigegebenen
                Handlungsempfehlung verwechselt wird.
              </p>
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-500">
              Derzeit liegt auch kein offener KI-Entwurf für eine
              Handlungsempfehlung vor.
            </p>
          )}

          <button
            onClick={onOpenAI}
            className="mt-5 rounded-xl bg-violet-700 px-4 py-2 text-sm font-semibold text-white"
          >
            KI-Vorschläge prüfen
          </button>
        </div>
      </div>
    );
  }

  const hasDocumentFacts = Boolean(summary.document_facts?.length);
  const hasDocumentReferences = Boolean(summary.relevant_document_ids?.length);
  const hasEvidenceBasis = hasDocumentFacts && hasDocumentReferences;

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-700">
              Handlungsempfehlung
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950">
              Was muss jetzt konkret getan werden?
            </h2>
          </div>
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
            Fachlich bestätigt
          </span>
        </div>

        <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
          <p className="text-sm font-semibold text-emerald-950">
            Freigegebene Handlungsempfehlung
          </p>
          <p className="mt-1 text-sm text-emerald-900">
            Diese Fassung wurde im Prüfprozess bestätigt. Die zugrunde liegenden
            Dokumente und Unsicherheiten bleiben zur Nachvollziehbarkeit sichtbar.
          </p>
        </div>

        <div className="mt-6 rounded-2xl border border-violet-200 bg-violet-50 p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-violet-700">
            Konkrete nächste Maßnahme
          </p>
          <p className="mt-2 text-lg font-semibold text-violet-950">
            {cleanAIText(summary.next_required_action) ||
              "Keine konkrete Handlung wurde bestätigt."}
          </p>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-slate-200 p-4">
            <p className="text-xs font-semibold uppercase text-slate-400">
              Verantwortlich
            </p>
            <p className="mt-2 font-semibold text-slate-900">
              {cleanAIText(summary.responsible_role) ||
                "Nicht eindeutig festgelegt"}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 p-4">
            <p className="text-xs font-semibold uppercase text-slate-400">
              Frist
            </p>
            <p className="mt-2 font-semibold text-slate-900">
              {dateLabel(summary.open_deadline)}
            </p>
            {summary.deadline_comment && (
              <p className="mt-2 text-sm text-slate-500">
                {cleanAIText(summary.deadline_comment)}
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="font-semibold text-slate-950">
            1. Bestätigte Fakten aus den Dokumenten
          </h3>
          {summary.document_facts?.length ? (
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-700">
              {summary.document_facts.map((fact, index) => (
                <li key={index}>{cleanAIText(fact)}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-500">
              Keine strukturierten Dokumentfakten hinterlegt.
            </p>
          )}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="font-semibold text-slate-950">2. Einordnung</h3>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">
            {cleanAIText(summary.interpretation) ||
              "Keine zusätzliche Einordnung hinterlegt."}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="font-semibold text-slate-950">
            3. Begründung aus der Evidenz
          </h3>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">
            {cleanAIText(summary.action_justification) ||
              "Keine gesonderte Begründung hinterlegt."}
          </p>
        </div>

        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
          <h3 className="font-semibold text-amber-950">
            4. Unsicherheit / noch zu prüfen
          </h3>
          {summary.uncertainty_notes?.length ? (
            <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-amber-900">
              {summary.uncertainty_notes.map((note, index) => (
                <li key={index}>{cleanAIText(note)}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-amber-800">
              Keine zusätzlichen offenen Punkte hinterlegt.
            </p>
          )}
        </div>
      </section>

      <section
        className={`rounded-2xl border bg-white p-5 ${
          hasEvidenceBasis ? "border-slate-200" : "border-amber-300"
        }`}
      >
        <div>
          <h3 className="font-semibold text-slate-950">Dokumentgrundlage</h3>
          <p className="mt-1 text-sm text-slate-500">
            {hasEvidenceBasis
              ? "Diese bestätigte Empfehlung enthält dokumentierte Fakten und konkrete Dokumentreferenzen."
              : "Die Empfehlung wurde zwar bestätigt, enthält aber keine vollständige strukturierte Dokumentgrundlage. Die Quellen sollten fachlich nachgeprüft werden."}
          </p>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {summary.relevant_document_ids?.length ? (
            summary.relevant_document_ids.map((id) => (
              <span
                key={id}
                className="rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-700"
              >
                {docMap.get(id) || `Dokument ${id}`}
              </span>
            ))
          ) : (
            <span className="text-sm text-slate-500">
              Keine Dokumentreferenz hinterlegt.
            </span>
          )}
        </div>
      </section>
    </div>
  );
}
