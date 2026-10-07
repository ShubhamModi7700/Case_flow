import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import {
  confirmDocumentCaseRoute,
  processDocument,
  suggestDocumentCase,
  type DocumentCaseRouteSuggestion,
} from "../services/ai";
import { useAuth } from "../AuthContext";
import DocumentFilePicker from "../components/documents/DocumentFilePicker";
import type { CaseItem, DocumentItem } from "../types";
import { formatCaseNumber } from "../types/case";
import { formatFileSize } from "../utils/fileHelpers";

function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => item?.msg)
        .filter(Boolean)
        .join("; ");

      if (messages) {
        return messages;
      }
    }

    if (status === 401) {
      return "Anmeldung erforderlich. Bitte melden Sie sich erneut an.";
    }

    if (status === 403) {
      return "Sie haben keine Berechtigung für diese Aktion.";
    }

    if (status === 404) {
      return "Die angeforderte Dokumentressource wurde nicht gefunden.";
    }

    if (status === 405) {
      return "Die Dokument-API-Route ist nicht korrekt konfiguriert.";
    }

    if (status) {
      return `${fallback} Server returned ${status}.`;
    }

    return "Das Backend konnte nicht erreicht werden.";
  }

  return fallback;
}

export default function DocumentsPage() {
  const { user } = useAuth();
  const canEdit = user?.role === "Manager" || user?.role === "User";
  const isManager = user?.role === "Manager";
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [busyDocumentId, setBusyDocumentId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [routeSuggestion, setRouteSuggestion] = useState<DocumentCaseRouteSuggestion | null>(null);
  const [routeCaseId, setRouteCaseId] = useState("");
  const [workflowCaseId, setWorkflowCaseId] = useState<number | null>(null);
  const [workflowStage, setWorkflowStage] = useState<
    "idle" | "uploaded" | "routing" | "route-review" | "analyzing" | "review-ready"
  >("idle");

  async function loadData(): Promise<void> {
    try {
      setLoading(true);
      setError("");

      const [caseResponse, documentResponse] = await Promise.all([
        api.get<CaseItem[]>("/cases/"),
        api.get<DocumentItem[]>("/documents"),
      ]);

      setCases(
        caseResponse.data.filter((item) => !item.is_archived),
      );
      setDocuments(documentResponse.data);
    } catch (requestError) {
      console.error("Loading documents failed:", requestError);
      setError(
        getErrorMessage(
          requestError,
          "Die Dokumente konnten nicht geladen werden.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  async function startAIWorkflow(document: DocumentItem): Promise<void> {
    setBusyDocumentId(document.id);
    setWorkflowCaseId(document.case_id ?? null);
    setRouteSuggestion(null);
    setRouteCaseId("");
    setNotice("");

    try {
      if (!document.case_id) {
        setWorkflowStage("routing");
        const suggestion = await suggestDocumentCase(document.id);
        setRouteSuggestion(suggestion);
        setRouteCaseId(suggestion.suggested_case_id ? String(suggestion.suggested_case_id) : "");
        setWorkflowStage("route-review");
        setNotice("Die KI hat die Fallzuordnung vorbereitet. Bitte bestätigen Sie den passenden Fall, bevor weitere Ergebnisse übernommen werden.");
        return;
      }

      setWorkflowStage("analyzing");
      if (document.embedding_status !== "Ready") {
        await processDocument(document.id);
      }
      setWorkflowCaseId(document.case_id);
      setWorkflowStage("review-ready");
      setNotice("Dokument hochgeladen und für die fallweite KI-Zusammenfassung indexiert.");
      await loadData();
    } catch (requestError) {
      setWorkflowStage("idle");
      throw requestError;
    } finally {
      setBusyDocumentId(null);
    }
  }

  async function uploadDocument(
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    if (!file) {
      setError("Bitte wählen Sie eine Datei aus.");
      return;
    }

    try {
      setUploading(true);
      setError("");

      const formData = new FormData();
      formData.append("file", file);

      if (description.trim()) {
        formData.append("description", description.trim());
      }

      if (selectedCaseId) {
        formData.append("case_id", selectedCaseId);
      }

      const response = await api.post<DocumentItem>("/documents", formData);

      setFile(null);
      setDescription("");
      setSelectedCaseId("");
      setWorkflowStage("uploaded");
      setNotice("Dokument hochgeladen. Die KI bereitet jetzt die Fallzuordnung und Handlungsvorschläge vor.");

      await loadData();
      await startAIWorkflow(response.data);
    } catch (requestError) {
      console.error("Document upload failed:", requestError);
      setError(
        getErrorMessage(
          requestError,
          "Das Dokument konnte nicht hochgeladen werden.",
        ),
      );
    } finally {
      setUploading(false);
    }
  }

  async function assignCase(
    documentId: number,
    caseId: string,
  ): Promise<void> {
    try {
      setBusyDocumentId(documentId);
      setError("");

      await api.patch(`/documents/${documentId}/case`, {
        case_id: caseId ? Number(caseId) : null,
      });

      await loadData();
    } catch (requestError) {
      console.error("Document assignment failed:", requestError);
      setError(
        getErrorMessage(
          requestError,
          "Die Dokumentzuordnung konnte nicht geändert werden.",
        ),
      );
    } finally {
      setBusyDocumentId(null);
    }
  }

  async function deleteDocument(
    documentId: number,
  ): Promise<void> {
    const confirmed = window.confirm(
      "Möchten Sie dieses Dokument wirklich dauerhaft löschen? Dieser Vorgang kann nicht rückgängig gemacht werden.",
    );

    if (!confirmed) {
      return;
    }

    try {
      setBusyDocumentId(documentId);
      setError("");

      await api.delete(`/documents/${documentId}`);
      await loadData();
    } catch (requestError) {
      console.error("Document deletion failed:", requestError);
      setError(
        getErrorMessage(
          requestError,
          "Das Dokument konnte nicht gelöscht werden.",
        ),
      );
    } finally {
      setBusyDocumentId(null);
    }
  }


  async function confirmSuggestedExistingCase(): Promise<void> {
    if (!routeSuggestion || !routeCaseId) {
      setError("Bitte wählen Sie einen bestehenden Fall aus.");
      return;
    }

    try {
      setBusyDocumentId(routeSuggestion.document_id);
      setError("");
      const result = await confirmDocumentCaseRoute(routeSuggestion.document_id, {
        action: "assign_existing",
        case_id: Number(routeCaseId),
      });
      setWorkflowStage("analyzing");
      setWorkflowCaseId(result.case_id);
      setWorkflowStage("review-ready");
      setRouteSuggestion(null);
      setRouteCaseId("");
      setNotice(`${result.message} Das Dokument ist für die fallweite KI-Zusammenfassung bereit.`);
      await loadData();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Die Fallzuordnung konnte nicht bestätigt werden."));
    } finally {
      setBusyDocumentId(null);
    }
  }

  async function confirmNewCase(): Promise<void> {
    if (!routeSuggestion?.new_case) {
      setError("Es liegt kein KI-Fallentwurf vor.");
      return;
    }

    try {
      setBusyDocumentId(routeSuggestion.document_id);
      setError("");
      const result = await confirmDocumentCaseRoute(routeSuggestion.document_id, {
        action: "create_new",
        new_case: routeSuggestion.new_case,
      });
      setWorkflowStage("analyzing");
      setWorkflowCaseId(result.case_id);
      setWorkflowStage("review-ready");
      setRouteSuggestion(null);
      setRouteCaseId("");
      setNotice(`${result.message} Das Dokument ist für die fallweite KI-Zusammenfassung bereit.`);
      await loadData();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Der neue Fall konnte nicht angelegt werden."));
    } finally {
      setBusyDocumentId(null);
    }
  }

  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) {
      return documents;
    }

    return documents.filter((item) =>
      [
        item.file_name,
        item.description,
        item.uploaded_by,
        item.company,
        item.department,
      ]
        .filter(Boolean)
        .some((value) =>
          String(value).toLowerCase().includes(query),
        ),
    );
  }, [documents, search]);

  return (
    <div className="mx-auto max-w-7xl px-8 py-8">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
          Case Flow
        </p>

        <h1 className="mt-2 text-3xl font-bold text-slate-950">
          Dokumente
        </h1>

        <p className="mt-2 text-sm text-slate-500">
          Dokument hochladen → Fall zuordnen → KI-Vorschläge prüfen → durch Benutzer freigeben.
        </p>
      </header>

      {workflowStage !== "idle" && (
        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Dokument-Workflow</p>
              <h2 className="mt-1 text-lg font-semibold text-slate-950">Vom Dokument zur bestätigten Maßnahme</h2>
            </div>
            {workflowStage === "review-ready" && workflowCaseId && (
              <Link to={`/cases/${workflowCaseId}`} className="rounded-xl bg-violet-700 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-600">
                KI-Vorschläge im Fall prüfen
              </Link>
            )}
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-5">
            {[
              ["uploaded", "1. Upload"],
              ["routing", "2. Fall erkennen"],
              ["route-review", "3. Zuordnung bestätigen"],
              ["analyzing", "4. Frist & Maßnahme"],
              ["review-ready", "5. Freigabe durch Benutzer"],
            ].map(([stage, label]) => {
              const order = ["uploaded", "routing", "route-review", "analyzing", "review-ready"];
              const current = order.indexOf(workflowStage);
              const item = order.indexOf(stage);
              const done = item < current || (workflowStage === "review-ready" && item === current);
              const active = item === current;
              return <div key={stage} className={`rounded-xl border px-3 py-3 text-sm font-medium ${active ? "border-violet-300 bg-violet-50 text-violet-900" : done ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-slate-50 text-slate-400"}`}>{label}</div>;
            })}
          </div>
          <p className="mt-3 text-xs text-slate-500">KI-Ergebnisse bleiben Vorschläge. Falldaten werden erst nach ausdrücklicher Benutzerbestätigung übernommen.</p>
        </section>
      )}

      {error && (
        <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {notice && (
        <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          {notice}
        </div>
      )}

      {routeSuggestion && (
        <section className="mt-6 rounded-2xl border border-violet-200 bg-violet-50 p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-600">
                KI-Fallzuordnung
              </p>
              <h2 className="mt-1 text-xl font-semibold text-slate-950">
                {routeSuggestion.decision === "new_case"
                  ? "Neuer Fall vorgeschlagen"
                  : routeSuggestion.decision === "existing_case"
                    ? "Bestehender Fall vorgeschlagen"
                    : "Fallzuordnung ist nicht eindeutig"}
              </h2>
            </div>
            <span className="rounded-full bg-white px-3 py-1 text-sm font-semibold text-violet-700">
              KI-Sicherheit {Math.round(routeSuggestion.confidence * 100)} %
            </span>
          </div>

          <p className="mt-4 text-sm leading-6 text-slate-700">
            {routeSuggestion.reason}
          </p>

          {routeSuggestion.new_case && (
            <div className="mt-5 grid gap-3 rounded-xl border border-violet-100 bg-white p-4 md:grid-cols-2">
              <div><span className="text-xs text-slate-500">Titel</span><p className="font-medium">{routeSuggestion.new_case.title}</p></div>
              <div><span className="text-xs text-slate-500">Unternehmen</span><p className="font-medium">{routeSuggestion.new_case.company ?? "Zu prüfen"}</p></div>
              <div><span className="text-xs text-slate-500">Kategorie</span><p>{routeSuggestion.new_case.category}</p></div>
              <div><span className="text-xs text-slate-500">Frist</span><p>{routeSuggestion.new_case.primary_deadline ?? "Keine erkannt"}</p></div>
              <div className="md:col-span-2"><span className="text-xs text-slate-500">Management-Zusammenfassung</span><p>{routeSuggestion.new_case.management_summary ?? "Keine"}</p></div>
              <div className="md:col-span-2"><span className="text-xs text-slate-500">Nächste Maßnahme</span><p>{routeSuggestion.new_case.next_action ?? "Keine"}</p></div>
            </div>
          )}

          <div className="mt-5 grid gap-3 md:grid-cols-[1fr_auto_auto]">
            <select
              value={routeCaseId}
              onChange={(event) => setRouteCaseId(event.target.value)}
              className="input"
            >
              <option value="">Bestehenden Fall auswählen...</option>
              {cases.map((item) => (
                <option key={item.id} value={item.id}>
                  {formatCaseNumber(item.id)} — {item.title}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={!routeCaseId || busyDocumentId === routeSuggestion.document_id}
              onClick={() => void confirmSuggestedExistingCase()}
              className="rounded-xl border border-violet-300 bg-white px-4 py-2 text-sm font-semibold text-violet-800 disabled:opacity-50"
            >
              Diesem Fall zuordnen
            </button>
            {routeSuggestion.new_case && (
              <button
                type="button"
                disabled={busyDocumentId === routeSuggestion.document_id}
                onClick={() => void confirmNewCase()}
                className="rounded-xl bg-violet-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                Neuen Fall erstellen
              </button>
            )}
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Es wird nichts automatisch zugeordnet oder angelegt. Erst Ihre Bestätigung speichert die Entscheidung.
          </p>
        </section>
      )}

      <div className="mt-8 grid gap-6 xl:grid-cols-[380px_1fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold">
            Dokument hochladen
          </h2>

          <p className="mt-2 text-sm text-slate-500">
            Maximale Dateigröße: 4,5 MB.
          </p>

          <form
            onSubmit={uploadDocument}
            className="mt-5 space-y-4"
          >
            <div>
              <label className="mb-2 block text-sm font-medium">
                Mit Fall verknüpfen (optional)
              </label>

              <select
                value={selectedCaseId}
                onChange={(event) =>
                  setSelectedCaseId(event.target.value)
                }
                className="input"
              >
                <option value="">Kein verknüpfter Fall</option>

                {cases.map((item) => (
                  <option key={item.id} value={item.id}>
                    {formatCaseNumber(item.id)} — {item.company}
                    {item.department
                      ? ` / ${item.department}`
                      : ""}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                Datei
              </label>

              <DocumentFilePicker
                file={file}
                onFileChange={setFile}
                disabled={uploading}
                onError={setError}
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                Beschreibung
              </label>

              <textarea
                value={description}
                onChange={(event) =>
                  setDescription(event.target.value)
                }
                rows={3}
                className="input"
              />
            </div>

            <button
              type="submit"
              disabled={uploading || !file}
              className="w-full rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {uploading
                ? "Wird hochgeladen..."
                : "Dokument hochladen"}
            </button>
          </form>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold">
                Alle Dokumente
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                {documents.length} Dokument(e)
              </p>
            </div>

            <input
              type="search"
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="Dokumente durchsuchen..."
              className="input max-w-xs"
            />
          </div>

          {loading ? (
            <p className="mt-6 text-sm text-slate-500">
              Dokumente werden geladen...
            </p>
          ) : filteredDocuments.length === 0 ? (
            <p className="mt-6 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">
              Keine Dokumente gefunden.
            </p>
          ) : (
            <div className="mt-6 divide-y divide-slate-100">
              {filteredDocuments.map((item) => {
                const isBusy =
                  busyDocumentId === item.id;

                return (
                  <div key={item.id} className="py-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="break-all font-medium text-slate-950">
                          {item.file_name}
                        </p>

                        <p className="mt-1 text-sm text-slate-500">
                          {item.description ??
                            "Keine Beschreibung"}
                        </p>

                        <p className="mt-1 text-xs text-slate-400">
                          {formatFileSize(item.file_size)} · Hochgeladen von{" "}
                          {item.uploaded_by ?? "Unbekannt"}
                        </p>

                        <p className="mt-2 text-xs font-medium text-slate-500">
                          Verarbeitung: {item.processing_status} · Embedding: {item.embedding_status}
                          {item.chunk_count > 0
                            ? ` · ${item.chunk_count} Textabschnitte`
                            : ""}
                        </p>

                        {item.processing_error && (
                          <p className="mt-1 text-xs text-red-600">
                            {item.processing_error}
                          </p>
                        )}
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {item.case_id && (
                          <Link
                            to={`/cases/${item.case_id}`}
                            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50"
                          >
                            Fall öffnen
                          </Link>
                        )}

                        {isManager && (
                          <button
                            type="button"
                            disabled={isBusy}
                            onClick={() =>
                              void deleteDocument(item.id)
                            }
                            className="rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                          >
                            Löschen
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="mt-3 max-w-md">
                      <label className="mb-1 block text-xs font-medium text-slate-500">
                        Verknüpfter Fall
                      </label>

                      <select
                        value={item.case_id ?? ""}
                        disabled={isBusy || !canEdit}
                        onChange={(event) =>
                          void assignCase(
                            item.id,
                            event.target.value,
                          )
                        }
                        className="input"
                      >
                        <option value="">
                          Kein verknüpfter Fall
                        </option>

                        {cases.map((caseItem) => (
                          <option
                            key={caseItem.id}
                            value={caseItem.id}
                          >
                            {formatCaseNumber(caseItem.id)} —{" "}
                            {caseItem.company}
                            {caseItem.department
                              ? ` / ${caseItem.department}`
                              : ""}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}