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
      await approveAISuggestion(pendingSuggestion.id, {
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
      setNotice("Die Dokumentvorschläge wurden bestätigt.");
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
              Fall schnell verstehen und handeln
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
          <div className="mt-6 grid gap-5 lg:grid-cols-2">
            <label className="lg:col-span-2">
              <span className="text-sm font-semibold text-slate-700">Kurze Fallzusammenfassung</span>
              <textarea
                rows={4}
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
                rows={3}
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
                rows={3}
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
              <p><strong>Status:</strong> {visibleSummary.status}</p>
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
          <h2 className="text-lg font-semibold text-amber-950">Dokumentvorschläge prüfen</h2>
          <p className="mt-1 text-sm text-amber-800">
            Vorgeschlagener Fall: CF-{String(pendingSuggestion.suggested_case_id || caseItem.id).padStart(4, "0")}
            {pendingSuggestion.case_match_confidence !== null
              ? ` · Übereinstimmung ${(pendingSuggestion.case_match_confidence * 100).toFixed(0)} %`
              : ""}
          </p>
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
                {working === "approve-suggestion" ? "Wird gespeichert..." : "Bestätigen und speichern"}
              </button>
              <button type="button" disabled={working !== null} onClick={() => void rejectSuggestion()} className="rounded-xl border border-red-200 bg-white px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50">
                Ablehnen
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
