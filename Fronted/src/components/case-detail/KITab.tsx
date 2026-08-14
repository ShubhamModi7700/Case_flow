import { useEffect, useMemo, useState } from "react";

import {
  analyzeDocument as requestDocumentAnalysis,
  approveAISuggestion,
  approveManagementSummary,
  generateManagementSummary,
  getCaseAISuggestions,
  getManagementSummaries,
  processDocument,
  rejectAISuggestion,
  rejectManagementSummary,
} from "../../services/ai";
import type {
  AISuggestion,
  CaseAISummary,
  CaseItem,
  DocumentItem,
  RiskLevel,
} from "../../types";

type KITabProps = {
  caseItem: CaseItem;
  documents: DocumentItem[];
  canEdit: boolean;
  isManager: boolean;
  onCaseChanged: () => Promise<void>;
};

function messageFromError(error: any, fallback: string): string {
  const detail = error?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

function formatDate(value: string | null): string {
  if (!value) return "Keine Frist erkannt";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("de-DE");
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    Pending: "Prüfung ausstehend",
    Approved: "Bestätigt",
    EditedAndApproved: "Bearbeitet und bestätigt",
    Rejected: "Abgelehnt",
    Outdated: "Nicht mehr aktuell",
  };
  return labels[status] ?? status;
}

function confidenceLabel(value: number | null): string {
  if (value === null) return "Keine Bewertung";
  if (value >= 0.9) return "Hohe Übereinstimmung";
  if (value >= 0.7) return "Mittlere Übereinstimmung";
  return "Niedrige Übereinstimmung";
}

function riskLabel(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    Low: "Niedrig",
    Medium: "Mittel",
    High: "Hoch",
  };
  return value ? labels[value] ?? value : "Nicht bewertet";
}

function displayValue(value: string | null | undefined, fallback = "Nicht angegeben"): string {
  return value?.trim() || fallback;
}

export default function KITab({
  caseItem,
  documents,
  canEdit,
  isManager,
  onCaseChanged,
}: KITabProps) {
  const [summaries, setSummaries] = useState<CaseAISummary[]>([]);
  const [suggestions, setSuggestions] = useState<AISuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const pendingSummary = useMemo(
    () => summaries.find((item) => item.status === "Pending"),
    [summaries],
  );
  const visibleSummary = useMemo(
    () =>
      pendingSummary ||
      summaries.find((item) => item.status === "Approved") ||
      summaries[0],
    [pendingSummary, summaries],
  );
  const pendingSuggestion = useMemo(
    () => suggestions.find((item) => item.status === "Pending"),
    [suggestions],
  );
  const approvedSuggestion = useMemo(
    () =>
      suggestions.find((item) =>
        ["Approved", "EditedAndApproved"].includes(item.status),
      ),
    [suggestions],
  );
  const documentsById = useMemo(
    () => new Map(documents.map((document) => [document.id, document])),
    [documents],
  );

  const [summaryForm, setSummaryForm] = useState({
    short_case_summary: "",
    latest_development: "",
    next_required_action: "",
    open_deadline: "",
    deadline_comment: "",
    risk: "" as "" | RiskLevel,
    risk_comment: "",
  });

  const [suggestionForm, setSuggestionForm] = useState({
    summary: "",
    latest_development: "",
    deadline: "",
    next_action: "",
    risk: "" as "" | RiskLevel,
    risk_reason: "",
  });

  async function loadAIData(): Promise<void> {
    try {
      setLoading(true);
      setError("");
      const [summaryData, suggestionData] = await Promise.all([
        getManagementSummaries(caseItem.id),
        getCaseAISuggestions(caseItem.id),
      ]);
      setSummaries(summaryData);
      setSuggestions(suggestionData);
    } catch (requestError) {
      setError(
        messageFromError(
          requestError,
          "Die KI-Daten konnten nicht geladen werden.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAIData();
  }, [caseItem.id]);

  useEffect(() => {
    if (!visibleSummary) return;
    setSummaryForm({
      short_case_summary: visibleSummary.short_case_summary || "",
      latest_development: visibleSummary.latest_development || "",
      next_required_action: visibleSummary.next_required_action || "",
      open_deadline: visibleSummary.open_deadline || "",
      deadline_comment: visibleSummary.deadline_comment || "",
      risk: (visibleSummary.suggested_risk || "") as "" | RiskLevel,
      risk_comment: visibleSummary.risk_comment || "",
    });
  }, [visibleSummary?.id]);

  useEffect(() => {
    if (!pendingSuggestion) return;
    setSuggestionForm({
      summary: pendingSuggestion.suggested_summary || "",
      latest_development:
        pendingSuggestion.suggested_latest_development || "",
      deadline: pendingSuggestion.suggested_deadline || "",
      next_action: pendingSuggestion.suggested_next_action || "",
      risk: (pendingSuggestion.suggested_risk || "") as "" | RiskLevel,
      risk_reason: pendingSuggestion.suggested_risk_reason || "",
    });
  }, [pendingSuggestion?.id]);

  async function generateSummary(): Promise<void> {
    try {
      setWorking("summary");
      setError("");
      setNotice("");
      await generateManagementSummary(caseItem.id);
      setNotice("Eine neue Management-Zusammenfassung wurde erstellt.");
      await loadAIData();
    } catch (requestError) {
      setError(
        messageFromError(
          requestError,
          "Die Management-Zusammenfassung konnte nicht erstellt werden.",
        ),
      );
    } finally {
      setWorking(null);
    }
  }

  async function approveSummary(): Promise<void> {
    if (!pendingSummary) return;
    try {
      setWorking("approve-summary");
      setError("");
      await approveManagementSummary(pendingSummary.id, {
        short_case_summary: summaryForm.short_case_summary || null,
        latest_development: summaryForm.latest_development || null,
        next_required_action: summaryForm.next_required_action || null,
        open_deadline: summaryForm.open_deadline || null,
        deadline_comment: summaryForm.deadline_comment || null,
        risk: isManager && summaryForm.risk ? summaryForm.risk : null,
        risk_comment: summaryForm.risk_comment || null,
        relevant_document_ids: pendingSummary.relevant_document_ids,
      });
      setNotice("Die Management-Zusammenfassung wurde bestätigt.");
      await Promise.all([loadAIData(), onCaseChanged()]);
    } catch (requestError) {
      setError(
        messageFromError(
          requestError,
          "Die Zusammenfassung konnte nicht bestätigt werden.",
        ),
      );
    } finally {
      setWorking(null);
    }
  }

  async function rejectSummary(): Promise<void> {
    if (!pendingSummary) return;
    try {
      setWorking("reject-summary");
      await rejectManagementSummary(pendingSummary.id);
      setNotice("Die Management-Zusammenfassung wurde abgelehnt.");
      await loadAIData();
    } catch (requestError) {
      setError(
        messageFromError(
          requestError,
          "Die Zusammenfassung konnte nicht abgelehnt werden.",
        ),
      );
    } finally {
      setWorking(null);
    }
  }

  async function analyzeDocument(document: DocumentItem): Promise<void> {
    try {
      setWorking(`document-${document.id}`);
      setError("");
      setNotice("");
      if (document.embedding_status !== "Ready") {
        await processDocument(document.id);
      }
      await requestDocumentAnalysis(document.id);
      setNotice(`KI-Analyse für „${document.file_name}“ wurde erstellt.`);
      await Promise.all([loadAIData(), onCaseChanged()]);
    } catch (requestError) {
      setError(
        messageFromError(
          requestError,
          `Das Dokument „${document.file_name}“ konnte nicht analysiert werden.`,
        ),
      );
    } finally {
      setWorking(null);
    }
  }

  async function approveSuggestion(): Promise<void> {
    if (!pendingSuggestion) return;
    try {
      setWorking("approve-suggestion");
      setError("");
      const result = await approveAISuggestion(pendingSuggestion.id, {
        selected_case_id: caseItem.id,
        summary: suggestionForm.summary || null,
        latest_development: suggestionForm.latest_development || null,
        deadline: suggestionForm.deadline || null,
        next_action: suggestionForm.next_action || null,
        risk:
          isManager && suggestionForm.risk
            ? suggestionForm.risk
            : null,
        risk_reason:
          isManager && suggestionForm.risk
            ? suggestionForm.risk_reason || null
            : null,
      });
      setNotice(
        result.management_summary_created
          ? "Die Dokumentanalyse wurde bestätigt. Eine neue Management-Empfehlung steht zur Prüfung bereit."
          : "Die Dokumentanalyse wurde bestätigt. Die Management-Empfehlung konnte nicht automatisch aktualisiert werden; bitte aktualisieren Sie sie manuell.",
      );
      await Promise.all([loadAIData(), onCaseChanged()]);
    } catch (requestError) {
      setError(
        messageFromError(
          requestError,
          "Die Dokumentvorschläge konnten nicht bestätigt werden.",
        ),
      );
    } finally {
      setWorking(null);
    }
  }

  async function rejectSuggestion(): Promise<void> {
    if (!pendingSuggestion) return;
    try {
      setWorking("reject-suggestion");
      await rejectAISuggestion(pendingSuggestion.id);
      setNotice("Die Dokumentvorschläge wurden abgelehnt.");
      await loadAIData();
    } catch (requestError) {
      setError(
        messageFromError(
          requestError,
          "Die Dokumentvorschläge konnten nicht abgelehnt werden.",
        ),
      );
    } finally {
      setWorking(null);
    }
  }

  if (loading) {
    return <div className="p-8 text-slate-500">KI-Daten werden geladen...</div>;
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}
      {notice && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          {notice}
        </div>
      )}

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              KI-Managementübersicht
            </p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">
              Fall im Detail verstehen und handeln
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              KI-generierter Vorschlag – bitte vor dem Speichern fachlich prüfen.
            </p>
          </div>
          {canEdit && (
            <button
              type="button"
              disabled={working !== null || documents.length === 0}
              onClick={() => void generateSummary()}
              className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {working === "summary"
                ? "Wird erstellt..."
                : visibleSummary
                  ? "Zusammenfassung aktualisieren"
                  : "KI-Zusammenfassung erstellen"}
            </button>
          )}
        </div>

        {!visibleSummary ? (
          <div className="mt-6 rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
            Noch keine KI-Management-Zusammenfassung vorhanden. Mindestens ein
            verarbeitetes Dokument ist für eine fundierte RAG-Auswertung empfohlen.
          </div>
        ) : (
          <>
            {pendingSummary && (
              <div className="mt-6 rounded-2xl border border-violet-200 bg-violet-50 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-700">Neue KI-Managementempfehlung</p>
                    <h3 className="mt-1 text-lg font-semibold text-slate-950">Aktuellen Fall mit dem KI-Vorschlag vergleichen</h3>
                    <p className="mt-1 text-sm text-slate-600">Bestätigte Dokumentanalysen dienen als Evidenz. Erst Ihre Bestätigung ändert die offiziellen Falldaten.</p>
                  </div>
                  <span className="rounded-full border border-violet-200 bg-white px-3 py-1 text-xs font-semibold text-violet-700">Prüfung ausstehend</span>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <div className="rounded-xl border border-violet-100 bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Risiko</p>
                    <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
                      <div><p className="text-xs text-slate-500">Aktuell</p><p className="mt-1 font-semibold">{riskLabel(caseItem.risk)}</p></div>
                      <div><p className="text-xs text-violet-600">KI-Vorschlag</p><p className="mt-1 font-semibold text-violet-900">{riskLabel(pendingSummary.suggested_risk)}</p></div>
                    </div>
                  </div>
                  <div className="rounded-xl border border-violet-100 bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Frist</p>
                    <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
                      <div><p className="text-xs text-slate-500">Aktuell</p><p className="mt-1 font-semibold">{formatDate(caseItem.primary_deadline)}</p></div>
                      <div><p className="text-xs text-violet-600">KI-Vorschlag</p><p className="mt-1 font-semibold text-violet-900">{formatDate(pendingSummary.open_deadline)}</p></div>
                    </div>
                  </div>
                  <div className="rounded-xl border border-violet-100 bg-white p-4 md:col-span-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Nächste Maßnahme</p>
                    <div className="mt-2 grid gap-3 md:grid-cols-2 text-sm">
                      <div><p className="text-xs text-slate-500">Aktuell</p><p className="mt-1 whitespace-pre-wrap">{displayValue(caseItem.next_action)}</p></div>
                      <div><p className="text-xs text-violet-600">KI-Vorschlag</p><p className="mt-1 whitespace-pre-wrap text-violet-950">{displayValue(pendingSummary.next_required_action)}</p></div>
                    </div>
                  </div>
                </div>
              </div>
            )}

          <div className="mt-6 grid gap-5 lg:grid-cols-2">
            <label className="lg:col-span-2">
              <span className="text-sm font-semibold text-slate-700">Kurze Fallzusammenfassung</span>
              <textarea
                rows={8}
                disabled={!pendingSummary || !canEdit}
                value={summaryForm.short_case_summary}
                onChange={(event) =>
                  setSummaryForm((current) => ({
                    ...current,
                    short_case_summary: event.target.value,
                  }))
                }
                className="mt-2 w-full rounded-xl border border-slate-300 p-3 text-sm disabled:bg-slate-50"
              />
            </label>
            <label>
              <span className="text-sm font-semibold text-slate-700">Letzte Entwicklung</span>
              <textarea
                rows={6}
                disabled={!pendingSummary || !canEdit}
                value={summaryForm.latest_development}
                onChange={(event) =>
                  setSummaryForm((current) => ({
                    ...current,
                    latest_development: event.target.value,
                  }))
                }
                className="mt-2 w-full rounded-xl border border-slate-300 p-3 text-sm disabled:bg-slate-50"
              />
            </label>
            <label>
              <span className="text-sm font-semibold text-slate-700">Nächste erforderliche Maßnahme</span>
              <textarea
                rows={6}
                disabled={!pendingSummary || !canEdit}
                value={summaryForm.next_required_action}
                onChange={(event) =>
                  setSummaryForm((current) => ({
                    ...current,
                    next_required_action: event.target.value,
                  }))
                }
                className="mt-2 w-full rounded-xl border border-slate-300 p-3 text-sm disabled:bg-slate-50"
              />
            </label>
            <label>
              <span className="text-sm font-semibold text-slate-700">Offene Frist</span>
              <input
                type="date"
                disabled={!pendingSummary || !canEdit}
                value={summaryForm.open_deadline}
                onChange={(event) =>
                  setSummaryForm((current) => ({
                    ...current,
                    open_deadline: event.target.value,
                  }))
                }
                className="mt-2 w-full rounded-xl border border-slate-300 p-3 text-sm disabled:bg-slate-50"
              />
              <p className="mt-1 text-xs text-slate-400">
                {formatDate(visibleSummary.open_deadline)}
              </p>
            </label>
            <label>
              <span className="text-sm font-semibold text-slate-700">Vorgeschlagenes Risiko</span>
              <select
                disabled={!pendingSummary || !isManager}
                value={summaryForm.risk}
                onChange={(event) =>
                  setSummaryForm((current) => ({
                    ...current,
                    risk: event.target.value as "" | RiskLevel,
                  }))
                }
                className="mt-2 w-full rounded-xl border border-slate-300 p-3 text-sm disabled:bg-slate-50"
              >
                <option value="">Nicht ändern</option>
                <option value="Low">Niedrig</option>
                <option value="Medium">Mittel</option>
                <option value="High">Hoch</option>
              </select>
            </label>
            <label>
              <span className="text-sm font-semibold text-slate-700">Risikohinweis</span>
              <textarea
                rows={3}
                disabled={!pendingSummary || !canEdit}
                value={summaryForm.risk_comment}
                onChange={(event) =>
                  setSummaryForm((current) => ({
                    ...current,
                    risk_comment: event.target.value,
                  }))
                }
                className="mt-2 w-full rounded-xl border border-slate-300 p-3 text-sm disabled:bg-slate-50"
              />
            </label>
            <div className="lg:col-span-2 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
              <p><strong>Status:</strong> {statusLabel(visibleSummary.status)}</p>
              <div className="mt-2">
                <strong>Relevante Dokumente:</strong>
                {visibleSummary.relevant_document_ids.length ? (
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    {visibleSummary.relevant_document_ids.map((documentId) => {
                      const document = documentsById.get(documentId);
                      return (
                        <li key={documentId}>
                          {document?.file_name || `Dokument ${documentId}`}
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <span className="ml-1">Keine sicher ermittelt</span>
                )}
              </div>
            </div>
          </div>
          </>
        )}

        {pendingSummary && canEdit && (
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              disabled={working !== null}
              onClick={() => void approveSummary()}
              className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {working === "approve-summary" ? "Wird gespeichert..." : "Bestätigen und veröffentlichen"}
            </button>
            <button
              type="button"
              disabled={working !== null}
              onClick={() => void rejectSummary()}
              className="rounded-xl border border-red-200 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
            >
              Ablehnen
            </button>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-950">Dokumentanalyse</h2>
        <p className="mt-1 text-sm text-slate-500">
          Dokumente werden extrahiert, eingebettet und anschließend mit RAG analysiert.
        </p>
        <div className="mt-5 space-y-3">
          {documents.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-300 p-5 text-sm text-slate-500">
              Noch keine Dokumente vorhanden.
            </p>
          ) : (
            documents.map((document) => (
              <div key={document.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-4">
                <div>
                  <p className="font-semibold text-slate-900">{document.file_name}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Verarbeitung: {document.processing_status} · Embedding: {document.embedding_status} · Chunks: {document.chunk_count}
                  </p>
                </div>
                {canEdit && (
                  <button
                    type="button"
                    disabled={working !== null}
                    onClick={() => void analyzeDocument(document)}
                    className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    {working === `document-${document.id}` ? "Wird analysiert..." : "Mit KI analysieren"}
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </section>

      {pendingSuggestion && (
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">✦ KI-Vorschlag</p>
              <h2 className="mt-2 text-lg font-semibold text-amber-950">Dokumentvorschläge prüfen</h2>
              <p className="mt-1 text-sm text-amber-800">
                Vorgeschlagener Fall: CF-{String(pendingSuggestion.suggested_case_id || caseItem.id).padStart(4, "0")}
              </p>
            </div>
            {pendingSuggestion.case_match_confidence !== null && (
              <div className="rounded-xl border border-amber-200 bg-white px-4 py-3 text-right">
                <p className="text-xs font-semibold uppercase tracking-wider text-amber-700">{confidenceLabel(pendingSuggestion.case_match_confidence)}</p>
                <p className="mt-1 text-2xl font-bold text-amber-950">{(pendingSuggestion.case_match_confidence * 100).toFixed(0)} %</p>
              </div>
            )}
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-amber-200 bg-white p-4 text-sm text-slate-700">
              <p className="font-semibold text-slate-900">Quelle</p>
              <p className="mt-1">{documentsById.get(pendingSuggestion.document_id)?.file_name || `Dokument ${pendingSuggestion.document_id}`}</p>
              {pendingSuggestion.deadline_source && (
                <p className="mt-2 text-xs leading-5 text-slate-500">Fristquelle: {pendingSuggestion.deadline_source}</p>
              )}
            </div>
            <div className="rounded-xl border border-amber-200 bg-white p-4 text-sm text-slate-700">
              <p className="font-semibold text-slate-900">RAG-Quellen</p>
              <p className="mt-1">{pendingSuggestion.relevant_document_ids.length} relevante Dokument(e) · {pendingSuggestion.relevant_chunk_ids.length} Textabschnitt(e)</p>
              {pendingSuggestion.relevant_document_ids.length > 0 && (
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  {pendingSuggestion.relevant_document_ids.map((id) => documentsById.get(id)?.file_name || `Dokument ${id}`).join(" · ")}
                </p>
              )}
            </div>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <label className="lg:col-span-2 text-sm font-semibold text-slate-700">
              Dokumentzusammenfassung
              <textarea rows={4} value={suggestionForm.summary} onChange={(event) => setSuggestionForm((current) => ({ ...current, summary: event.target.value }))} className="mt-2 w-full rounded-xl border border-amber-200 bg-white p-3 font-normal" />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Letzte Entwicklung
              <textarea rows={3} value={suggestionForm.latest_development} onChange={(event) => setSuggestionForm((current) => ({ ...current, latest_development: event.target.value }))} className="mt-2 w-full rounded-xl border border-amber-200 bg-white p-3 font-normal" />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Nächste Maßnahme
              <textarea rows={3} value={suggestionForm.next_action} onChange={(event) => setSuggestionForm((current) => ({ ...current, next_action: event.target.value }))} className="mt-2 w-full rounded-xl border border-amber-200 bg-white p-3 font-normal" />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Erkannte Frist
              <input type="date" value={suggestionForm.deadline} onChange={(event) => setSuggestionForm((current) => ({ ...current, deadline: event.target.value }))} className="mt-2 w-full rounded-xl border border-amber-200 bg-white p-3 font-normal" />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Vorgeschlagenes Risiko
              <select disabled={!isManager} value={suggestionForm.risk} onChange={(event) => setSuggestionForm((current) => ({ ...current, risk: event.target.value as "" | RiskLevel }))} className="mt-2 w-full rounded-xl border border-amber-200 bg-white p-3 font-normal disabled:bg-slate-100">
                <option value="">Nicht übernehmen</option>
                <option value="Low">Niedrig</option>
                <option value="Medium">Mittel</option>
                <option value="High">Hoch</option>
              </select>
            </label>
            <label className="lg:col-span-2 text-sm font-semibold text-slate-700">
              Risikobegründung
              <textarea rows={2} disabled={!isManager} value={suggestionForm.risk_reason} onChange={(event) => setSuggestionForm((current) => ({ ...current, risk_reason: event.target.value }))} className="mt-2 w-full rounded-xl border border-amber-200 bg-white p-3 font-normal disabled:bg-slate-100" />
            </label>
          </div>
          {canEdit && (
            <div className="mt-5 flex flex-wrap gap-3">
              <button type="button" disabled={working !== null} onClick={() => void approveSuggestion()} className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50">
                {working === "approve-suggestion" ? "Wird gespeichert..." : "Dokumentanalyse bestätigen"}
              </button>
              <button type="button" disabled={working !== null} onClick={() => void rejectSuggestion()} className="rounded-xl border border-red-200 bg-white px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50">
                Ablehnen
              </button>
            </div>
          )}
        </section>
      )}

      {!pendingSuggestion && approvedSuggestion && (
        <section className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">✓ Letzte bestätigte Dokumentanalyse</p>
              <h2 className="mt-2 text-lg font-semibold text-slate-950">Bestätigte Dokument-Evidenz</h2>
              <p className="mt-1 text-sm text-slate-600">
                Quelle: {documentsById.get(approvedSuggestion.document_id)?.file_name || `Dokument ${approvedSuggestion.document_id}`}
              </p>
            </div>
            <span className="rounded-full border border-emerald-200 bg-white px-3 py-1 text-xs font-semibold text-emerald-700">
              {statusLabel(approvedSuggestion.status)}
            </span>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <div className="lg:col-span-2 rounded-xl border border-emerald-100 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Dokumentzusammenfassung</p>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{approvedSuggestion.suggested_summary || "Keine Zusammenfassung gespeichert."}</p>
            </div>
            <div className="rounded-xl border border-emerald-100 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Letzte Entwicklung</p>
              <p className="mt-2 text-sm leading-6 text-slate-700">{approvedSuggestion.suggested_latest_development || "Nicht angegeben"}</p>
            </div>
            <div className="rounded-xl border border-emerald-100 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Nächste Maßnahme</p>
              <p className="mt-2 text-sm leading-6 text-slate-700">{approvedSuggestion.suggested_next_action || "Nicht angegeben"}</p>
            </div>
            <div className="rounded-xl border border-emerald-100 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Erkannte Frist</p>
              <p className="mt-2 text-sm font-semibold text-slate-900">{formatDate(approvedSuggestion.suggested_deadline)}</p>
            </div>
            <div className="rounded-xl border border-emerald-100 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Risikohinweis</p>
              <p className="mt-2 text-sm font-semibold text-slate-900">{approvedSuggestion.suggested_risk || "Nicht angegeben"}</p>
              {approvedSuggestion.suggested_risk_reason && <p className="mt-1 text-sm leading-6 text-slate-600">{approvedSuggestion.suggested_risk_reason}</p>}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
