import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api";
import {
  confirmDocumentCaseRoute,
  processDocument,
  suggestDocumentCase,
  type DocumentCaseRouteSuggestion,
} from "../services/ai";
import { useAuth } from "../AuthContext";
import type { CaseItem, DocumentItem } from "../types";
import { formatCaseNumber } from "../types/case";
import { formatFileSize } from "../utils/fileHelpers";

const DIRECT_UPLOAD_MAX_BYTES = 100 * 1024 * 1024;
const DIRECT_UPLOAD_EXTENSIONS = new Set([".pdf", ".docx", ".xlsx", ".eml", ".msg"]);

function validateDirectUpload(file: File): string | null {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!DIRECT_UPLOAD_EXTENSIONS.has(extension)) {
    return "Nicht unterstütztes Format (PDF, DOCX, XLSX, EML oder MSG).";
  }
  if (file.size === 0) return "Die Datei ist leer.";
  if (file.size > DIRECT_UPLOAD_MAX_BYTES) return "Die Datei überschreitet 100 MB.";
  return null;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;

    if (typeof detail === "string") return detail;

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => item?.msg)
        .filter(Boolean)
        .join("; ");
      if (messages) return messages;
    }

    if (status === 401)
      return "Anmeldung erforderlich. Bitte melden Sie sich erneut an.";
    if (status === 403)
      return "Sie haben keine Berechtigung für diese Aktion.";
    if (status === 404)
      return "Die angeforderte Dokumentressource wurde nicht gefunden.";
    if (status === 405)
      return "Die Dokument-API-Route ist nicht korrekt konfiguriert.";
    if (status) return `${fallback} Server returned ${status}.`;

    return "Das Backend konnte nicht erreicht werden.";
  }

  return fallback;
}

// Show case number, title and company consistently in every selector.
function getCaseLabel(item: CaseItem): string {
  const caseNumber = formatCaseNumber(item.id);
  const title = item.title?.trim();
  const company = item.company?.trim();

  return [
    caseNumber,
    title,
    company && company !== title ? company : null,
  ]
    .filter(Boolean)
    .join(" — ");
}

type RoutingEvent = {
  id: string;
  event_type: string;
  decision: string;
  suggested_case_id: number | null;
  assigned_case_id: number | null;
  confidence: number | null;
  reason: string | null;
  details: { candidates?: Array<{ case_id: number; title: string; similarity: number | null }>; previous_case_id?: number | null } | null;
  created_at: string | null;
};

type UploadBatchItem = {
  id: string;
  filename: string;
  document_id: number | null;
  status: string;
  error: string | null;
};
type UploadBatch = {
  id: string;
  created_at: string;
  case_id: number | null;
  total: number;
  counts: Record<string, number>;
  items: UploadBatchItem[];
};

export default function DocumentsPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();

  const canEdit = user?.role === "Manager" || user?.role === "User";
  const isManager = user?.role === "Manager";

  const [cases, setCases] = useState<CaseItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResults, setUploadResults] = useState<string[]>([]);
  const [uploadBatches, setUploadBatches] = useState<UploadBatch[]>([]);
  const [batchBusyId, setBatchBusyId] = useState<string | null>(null);
  const [historyDocumentId, setHistoryDocumentId] = useState<number | null>(null);
  const [routingHistory, setRoutingHistory] = useState<RoutingEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [description, setDescription] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [caseFilter, setCaseFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [showUpload, setShowUpload] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [busyDocumentId, setBusyDocumentId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [routeSuggestion, setRouteSuggestion] =
    useState<DocumentCaseRouteSuggestion | null>(null);
  const [routeCaseId, setRouteCaseId] = useState("");
  const [workflowCaseId, setWorkflowCaseId] = useState<number | null>(null);
  const [workflowStage, setWorkflowStage] = useState<
    "idle" | "uploaded" | "routing" | "route-review" | "analyzing" | "review-ready"
  >("idle");

  async function refreshBatches(): Promise<void> {
    try {
      const response = await api.get<UploadBatch[]>("/documents/batches");
      setUploadBatches(response.data);
    } catch (requestError) {
      console.error("Loading upload batches failed:", requestError);
    }
  }

  useEffect(() => {
    if (!canEdit) return;
    void refreshBatches();
    const interval = window.setInterval(() => void refreshBatches(), 15000);
    return () => window.clearInterval(interval);
  }, [canEdit]);

  async function retryBatchDocument(item: UploadBatchItem): Promise<void> {
    if (!item.document_id) {
      setError("Bitte wählen Sie die fehlgeschlagene Datei erneut zum Hochladen aus.");
      return;
    }
    try {
      setBatchBusyId(item.id);
      setError("");
      await api.post(`/documents/batches/items/${item.id}/retry`);
      await refreshBatches();
      setNotice(`Verarbeitung von ${item.filename} erneut eingeplant.`);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Erneute Verarbeitung fehlgeschlagen."));
    } finally {
      setBatchBusyId(null);
    }
  }

  async function resumeBatchUpload(item: UploadBatchItem, file: File, caseId: number | null): Promise<void> {
    if (file.name !== item.filename) {
      setError(`Bitte dieselbe Datei auswählen: ${item.filename}`);
      return;
    }
    const invalid = validateDirectUpload(file);
    if (invalid) {
      setError(invalid);
      return;
    }
    try {
      setBatchBusyId(item.id);
      setError("");
      const init = await api.post<{ upload_url: string; upload_token: string }>(
        "/documents/upload-init",
        { filename: file.name, batch_item_id: item.id, file_size: file.size,
          content_type: file.type || "application/octet-stream", case_id: caseId, description: null },
      );
      await axios.put(init.data.upload_url, file, {
        headers: { "Content-Type": file.type || "application/octet-stream" },
        timeout: 180000,
      });
      await api.post("/documents/upload-complete", { upload_token: init.data.upload_token });
      setNotice(`${file.name} erfolgreich erneut hochgeladen.`);
      await Promise.all([refreshBatches(), loadData()]);
    } catch (requestError) {
      const message = getErrorMessage(requestError, "Erneuter Upload fehlgeschlagen.");
      setError(message);
      try {
        await api.post(`/documents/batches/items/${item.id}/failed`, { message });
      } catch (reportError) {
        console.error("Could not persist upload failure:", reportError);
      }
      await refreshBatches();
    } finally {
      setBatchBusyId(null);
    }
  }

  async function loadData(): Promise<void> {
    try {
      setLoading(true);
      setError("");

      const [caseResponse, documentResponse] = await Promise.all([
        api.get<CaseItem[]>("/cases/"),
        api.get<DocumentItem[]>("/documents"),
      ]);

      const availableCases = caseResponse.data
        .filter((item) => !item.is_archived)
        .sort((a, b) => a.id - b.id);

      setCases(availableCases);

      const requestedCaseId = searchParams.get("case_id");

      if (
        requestedCaseId &&
        availableCases.some((item) => String(item.id) === requestedCaseId)
      ) {
        setSelectedCaseId(requestedCaseId);
      }

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
        setRouteCaseId(
          suggestion.suggested_case_id
            ? String(suggestion.suggested_case_id)
            : "",
        );
        setWorkflowStage("route-review");
        setNotice(
          "Die KI hat die Fallzuordnung vorbereitet. Bitte bestätigen Sie den passenden Fall, bevor weitere Ergebnisse übernommen werden.",
        );
        return;
      }

      setWorkflowStage("analyzing");

      if (document.embedding_status !== "Ready") {
        await processDocument(document.id);
      }

      setWorkflowCaseId(document.case_id);
      setWorkflowStage("review-ready");
      setNotice(
        "Dokument hochgeladen und für die fallweite KI-Zusammenfassung indexiert.",
      );

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

    if (files.length === 0) {
      setError("Bitte wählen Sie mindestens eine Datei aus.");
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setUploadResults([]);
    setError("");
    setNotice("");

    const failed: File[] = [];
    const results: string[] = [];
    let succeeded = 0;
    let singleUploaded: DocumentItem | null = null;

    const selectedFiles = [...files];
    let batchItems: { id: string; filename: string }[];
    try {
      const batch = await api.post<{ id: string; items: { id: string; filename: string }[] }>(
        "/documents/batches",
        { filenames: selectedFiles.map((file) => file.name),
          case_id: selectedCaseId ? Number(selectedCaseId) : null },
      );
      batchItems = batch.data.items;
      await refreshBatches();
    } catch (requestError) {
      setUploading(false);
      setError(getErrorMessage(requestError, "Upload-Batch konnte nicht erstellt werden."));
      return;
    }
    let nextFile = 0;
    async function uploadOne(currentFile: File, batchItemId: string): Promise<void> {
      try {
        const validationError = validateDirectUpload(currentFile);
        if (validationError) throw new Error(validationError);
        const init = await api.post<{
          upload_url: string;
          upload_token: string;
        }>("/documents/upload-init", {
          filename: currentFile.name,
          batch_item_id: batchItemId,
          file_size: currentFile.size,
          content_type: currentFile.type || "application/octet-stream",
          case_id: selectedCaseId ? Number(selectedCaseId) : null,
          description: description.trim() || null,
        });
        // File bytes go straight to Supabase, never through a Vercel Function.
        await axios.put(init.data.upload_url, currentFile, {
          headers: { "Content-Type": currentFile.type || "application/octet-stream" },
          timeout: 180000,
        });
        const response = await api.post<DocumentItem>(
          "/documents/upload-complete",
          { upload_token: init.data.upload_token },
        );

        succeeded += 1;
        singleUploaded = response.data;
        const outcome = `✓ ${currentFile.name}`;
        results.push(outcome);
        setUploadResults((previous) => [...previous, outcome]);
      } catch (requestError) {
        failed.push(currentFile);
        const message = requestError instanceof Error && !axios.isAxiosError(requestError)
          ? requestError.message
          : getErrorMessage(requestError, "Upload fehlgeschlagen.");
        try {
          await api.post(`/documents/batches/items/${batchItemId}/failed`, { message });
        } catch (reportError) {
          console.error("Could not persist upload failure:", reportError);
        }
        const outcome = `✗ ${currentFile.name}: ${message}`;
        results.push(outcome);
        setUploadResults((previous) => [...previous, outcome]);
      }

      setUploadProgress((previous) => previous + 1);
    }

    async function worker(): Promise<void> {
      while (nextFile < selectedFiles.length) {
        const index = nextFile++;
        await uploadOne(selectedFiles[index], batchItems[index].id);
      }
    }
    await Promise.all(Array.from({ length: Math.min(3, selectedFiles.length) }, () => worker()));

    setFiles(failed);
    setUploading(false);
    await refreshBatches();

    if (succeeded > 0) {
      setNotice(
        `${succeeded} von ${results.length} Dokumenten gespeichert. Die Extraktion und KI-Verarbeitung erfolgen separat.`,
      );

      try {
        await loadData();
      } catch (refreshError) {
        console.error(refreshError);
      }

      const uploadedDocument = singleUploaded as DocumentItem | null;
      if (
        results.length === 1 &&
        uploadedDocument &&
        !uploadedDocument.case_id
      ) {
        try {
          await startAIWorkflow(uploadedDocument);
        } catch (workflowError) {
          setError(
            getErrorMessage(
              workflowError,
              "Die KI-Fallzuordnung konnte nicht gestartet werden.",
            ),
          );
        }
      }
    }

    if (failed.length > 0) {
      setError(
        `${failed.length} Dokument(e) fehlgeschlagen. Sie können die fehlgeschlagenen Dateien erneut hochladen.`,
      );
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

  async function toggleRoutingHistory(documentId: number): Promise<void> {
    if (historyDocumentId === documentId) {
      setHistoryDocumentId(null);
      return;
    }
    setHistoryDocumentId(documentId);
    setRoutingHistory([]);
    setHistoryLoading(true);
    try {
      const response = await api.get<RoutingEvent[]>(`/documents/${documentId}/case-routing-history`);
      setRoutingHistory(response.data);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Fallzuordnungs-Verlauf konnte nicht geladen werden."));
    } finally {
      setHistoryLoading(false);
    }
  }

  async function deleteDocument(documentId: number): Promise<void> {
    const confirmed = window.confirm(
      "Möchten Sie dieses Dokument wirklich dauerhaft löschen? Dieser Vorgang kann nicht rückgängig gemacht werden.",
    );

    if (!confirmed) return;

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

      const result = await confirmDocumentCaseRoute(
        routeSuggestion.document_id,
        {
          action: "assign_existing",
          case_id: Number(routeCaseId),
        },
      );

      setWorkflowStage("analyzing");
      setWorkflowCaseId(result.case_id);
      setWorkflowStage("review-ready");
      setRouteSuggestion(null);
      setRouteCaseId("");
      setNotice(
        `${result.message} Das Dokument ist für die fallweite KI-Zusammenfassung bereit.`,
      );

      await loadData();
    } catch (requestError) {
      setError(
        getErrorMessage(
          requestError,
          "Die Fallzuordnung konnte nicht bestätigt werden.",
        ),
      );
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

      const result = await confirmDocumentCaseRoute(
        routeSuggestion.document_id,
        {
          action: "create_new",
          new_case: routeSuggestion.new_case,
        },
      );

      setWorkflowStage("analyzing");
      setWorkflowCaseId(result.case_id);
      setWorkflowStage("review-ready");
      setRouteSuggestion(null);
      setRouteCaseId("");
      setNotice(
        `${result.message} Das Dokument ist für die fallweite KI-Zusammenfassung bereit.`,
      );

      await loadData();
    } catch (requestError) {
      setError(
        getErrorMessage(
          requestError,
          "Der neue Fall konnte nicht angelegt werden.",
        ),
      );
    } finally {
      setBusyDocumentId(null);
    }
  }

  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();
    return documents.filter((item) => {
      const matchesSearch = !query || [
        item.file_name, item.description, item.uploaded_by,
        item.company, item.department,
        item.case_id ? formatCaseNumber(item.case_id) : "",
      ].filter(Boolean).some((value) => String(value).toLowerCase().includes(query));
      const matchesCase = caseFilter === "all" ||
        (caseFilter === "none" ? !item.case_id : String(item.case_id) === caseFilter);
      const matchesStatus = statusFilter === "all" ||
        (statusFilter === "ready"
          ? item.processing_status === "Ready" && item.embedding_status === "Ready"
          : statusFilter === "partial"
            ? item.processing_status === "Partial"
          : statusFilter === "failed"
            ? ["Failed", "Error"].includes(item.processing_status) || ["Failed", "Error"].includes(item.embedding_status)
            : !["Ready", "Partial"].includes(item.processing_status) &&
              !["Failed", "Error"].includes(item.processing_status) &&
              !["Failed", "Error"].includes(item.embedding_status));
      return matchesSearch && matchesCase && matchesStatus;
    });
  }, [documents, search, caseFilter, statusFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredDocuments.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visibleDocuments = filteredDocuments.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const readyCount = documents.filter((item) => item.processing_status === "Ready" && item.embedding_status === "Ready").length;
  const partialCount = documents.filter((item) => item.processing_status === "Partial").length;
  const failedCount = documents.filter((item) => ["Failed", "Error"].includes(item.processing_status) || ["Failed", "Error"].includes(item.embedding_status)).length;
  const pendingCount = documents.filter((item) =>
    !["Ready", "Partial"].includes(item.processing_status) &&
    !["Failed", "Error"].includes(item.processing_status) &&
    !["Failed", "Error"].includes(item.embedding_status)
  ).length;

  return (
    <div className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 lg:px-10">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
          Case Flow
        </p>

        <h1 className="mt-2 text-3xl font-bold text-slate-950">
          Dokumente
        </h1>

        </div>
        {canEdit && <button type="button" onClick={() => setShowUpload((value) => !value)} className="rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-slate-800">
          {showUpload ? "Upload schließen" : "+ Dokumente hochladen"}
        </button>}
      </header>

      <div className="mt-7 grid grid-cols-2 gap-3 lg:grid-cols-5">
        {[
          ["Alle Dokumente", documents.length],
          ["bereit", readyCount],
          ["Teilweise verarbeitet", partialCount],
          ["Verarbeitung ausstehend", pendingCount],
          ["Fehler", failedCount],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">{label}</p>
            <p className="mt-2 text-2xl font-bold text-slate-950">{value}</p>
          </div>
        ))}
      </div>

      {workflowStage !== "idle" && (
        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                Dokument-Workflow
              </p>
              <h2 className="mt-1 text-lg font-semibold text-slate-950">
                Vom Dokument zur bestätigten Maßnahme
              </h2>
            </div>

            {workflowStage === "review-ready" && workflowCaseId && (
              <Link
                to={`/cases/${workflowCaseId}`}
                className="rounded-xl bg-violet-700 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-600"
              >
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
              const order = [
                "uploaded",
                "routing",
                "route-review",
                "analyzing",
                "review-ready",
              ];

              const current = order.indexOf(workflowStage);
              const item = order.indexOf(stage);
              const done =
                item < current ||
                (workflowStage === "review-ready" && item === current);
              const active = item === current;

              return (
                <div
                  key={stage}
                  className={`rounded-xl border px-3 py-3 text-sm font-medium ${
                    active
                      ? "border-violet-300 bg-violet-50 text-violet-900"
                      : done
                        ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                        : "border-slate-200 bg-slate-50 text-slate-400"
                  }`}
                >
                  {label}
                </div>
              );
            })}
          </div>

          <p className="mt-3 text-xs text-slate-500">
            KI-Ergebnisse bleiben Vorschläge. Falldaten werden erst
            nach ausdrücklicher Benutzerbestätigung übernommen.
          </p>
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
              KI-Sicherheit{" "}
              {Math.round(routeSuggestion.confidence * 100)} %
            </span>
          </div>

          <p className="mt-4 text-sm leading-6 text-slate-700">
            {routeSuggestion.reason}
          </p>

          {routeSuggestion.candidates.length > 0 && (
            <div className="mt-4 rounded-xl border border-violet-100 bg-white p-4">
              <h3 className="text-sm font-semibold text-slate-800">Verglichene Fälle (Vektorsuche)</h3>
              <p className="mt-1 text-xs text-slate-500">Ähnlichkeit ist keine kalibrierte Wahrscheinlichkeit. Bitte den Inhalt prüfen.</p>
              <ul className="mt-2 space-y-2 text-sm">
                {routeSuggestion.candidates.map((candidate) => (
                  <li key={candidate.case_id} className="flex flex-wrap items-center justify-between gap-2">
                    <span>{candidate.title} (#{candidate.case_id})</span>
                    <span className="text-slate-500">Ähnlichkeit: {candidate.similarity == null ? "–" : candidate.similarity.toFixed(3)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {routeSuggestion.new_case && (
            <div className="mt-5 grid gap-3 rounded-xl border border-violet-100 bg-white p-4 md:grid-cols-2">
              <div>
                <span className="text-xs text-slate-500">Titel</span>
                <p className="font-medium">
                  {routeSuggestion.new_case.title}
                </p>
              </div>

              <div>
                <span className="text-xs text-slate-500">
                  Unternehmen
                </span>
                <p className="font-medium">
                  {routeSuggestion.new_case.company ?? "Zu prüfen"}
                </p>
              </div>

              <div>
                <span className="text-xs text-slate-500">
                  Kategorie
                </span>
                <p>{routeSuggestion.new_case.category}</p>
              </div>

              <div>
                <span className="text-xs text-slate-500">Frist</span>
                <p>
                  {routeSuggestion.new_case.primary_deadline ??
                    "Keine erkannt"}
                </p>
              </div>

              <div className="md:col-span-2">
                <span className="text-xs text-slate-500">
                  Management-Zusammenfassung
                </span>
                <p>
                  {routeSuggestion.new_case.management_summary ??
                    "Keine"}
                </p>
              </div>

              <div className="md:col-span-2">
                <span className="text-xs text-slate-500">
                  Nächste Maßnahme
                </span>
                <p>
                  {routeSuggestion.new_case.next_action ?? "Keine"}
                </p>
              </div>
            </div>
          )}

          <div className="mt-5 grid gap-3 md:grid-cols-[1fr_auto_auto]">
            <select
              value={routeCaseId}
              onChange={(event) =>
                setRouteCaseId(event.target.value)
              }
              className="input"
            >
              <option value="">
                Bestehenden Fall auswählen...
              </option>

              {cases.map((item) => (
                <option key={item.id} value={item.id}>
                  {getCaseLabel(item)}
                </option>
              ))}
            </select>

            <button
              type="button"
              disabled={
                !routeCaseId ||
                busyDocumentId === routeSuggestion.document_id
              }
              onClick={() =>
                void confirmSuggestedExistingCase()
              }
              className="rounded-xl border border-violet-300 bg-white px-4 py-2 text-sm font-semibold text-violet-800 disabled:opacity-50"
            >
              Diesem Fall zuordnen
            </button>

            {routeSuggestion.new_case && (
              <button
                type="button"
                disabled={
                  busyDocumentId === routeSuggestion.document_id
                }
                onClick={() => void confirmNewCase()}
                className="rounded-xl bg-violet-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                Neuen Fall erstellen
              </button>
            )}
          </div>

          <p className="mt-3 text-xs text-slate-500">
            Es wird nichts automatisch zugeordnet oder angelegt.
            Erst Ihre Bestätigung speichert die Entscheidung.
          </p>
        </section>
      )}

      {canEdit && (
        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Upload-Batches (dauerhaft gespeichert)</h2>
            <button type="button" onClick={() => void refreshBatches()}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
              Status aktualisieren
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Die letzten 25 Batches dieses Benutzerkontos. Verarbeitung wird alle 15 Sekunden abgefragt.
            Nach einem Browser-Neustart bleiben Upload- und Verarbeitungsstände erhalten.
          </p>
          {uploadBatches.length === 0 && <p className="mt-3 text-sm text-slate-500">Noch keine Upload-Batches.</p>}
          <div className="mt-4 space-y-3">
            {uploadBatches.map((batch) => (
              <details key={batch.id} className="rounded-xl border border-slate-200 p-3">
                <summary className="cursor-pointer text-sm font-semibold">
                  {new Date(batch.created_at).toLocaleString("de-DE")} — {batch.total} Dateien
                  {" · "}Bereit: {batch.counts.Ready ?? 0}
                  {" · "}Teilweise: {batch.counts.Partial ?? 0}
                  {" · "}Fehler: {batch.counts.Failed ?? 0}
                  {" · "}Offen: {batch.total - (batch.counts.Ready ?? 0) - (batch.counts.Partial ?? 0) - (batch.counts.Failed ?? 0)}
                </summary>
                <ul className="mt-3 space-y-2 text-sm">
                  {batch.items.map((item) => (
                    <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2">
                      <span className="min-w-0 break-all">{item.filename} — <strong>{item.status}</strong>
                        {item.error && <span className="block text-xs text-red-700">{item.error}</span>}
                      </span>
                      {!item.document_id && (
                        <label className="cursor-pointer rounded-lg border border-slate-300 px-3 py-1 text-xs">
                          Datei erneut auswählen
                          <input type="file" className="sr-only" disabled={batchBusyId === item.id}
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              if (file) void resumeBatchUpload(item, file, batch.case_id);
                              event.target.value = "";
                            }} />
                        </label>
                      )}
                      {(item.status === "Failed" || item.status === "Partial") && item.document_id && (
                        <button type="button" disabled={batchBusyId === item.id}
                          onClick={() => void retryBatchDocument(item)}
                          className="rounded-lg border border-slate-300 px-3 py-1 text-xs disabled:opacity-50">
                          Verarbeitung wiederholen
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            ))}
          </div>
        </section>
      )}

      <div className="mt-7 space-y-6">
        {showUpload && canEdit && <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold">
            Dokumente hochladen
          </h2>


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
                <option value="">
                  Kein verknüpfter Fall
                </option>

                {cases.map((item) => (
                  <option key={item.id} value={item.id}>
                    {getCaseLabel(item)}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                Datei
              </label>

              <input
                type="file"
                multiple
                accept=".pdf,.docx,.xlsx,.eml,.msg"
                disabled={uploading}
                onChange={(event) => {
                  setFiles(Array.from(event.target.files ?? []));
                  setUploadResults([]);
                  setUploadProgress(0);
                  setError("");
                }}
                className="block w-full rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm"
              />

              <p className="mt-2 text-xs text-slate-500">
                Mehrere Dateien auswählen. Unterstützt: PDF, DOCX, XLSX, EML, MSG;
                maximal 100 MB pro Datei. Direkter Upload zu Supabase Storage.
                Ohne Fallauswahl bleiben Dokumente zunächst unzugeordnet.
              </p>

              {files.length > 0 && (
                <p className="mt-2 text-sm text-slate-700">
                  {files.length} Datei(en) ausgewählt
                </p>
              )}

              {uploadResults.length > 0 && (
                <ul
                  className="mt-3 max-h-36 overflow-y-auto text-xs"
                  aria-label="Upload-Ergebnisse"
                >
                  {uploadResults.map((result, index) => (
                    <li key={index} className="py-1">
                      {result}
                    </li>
                  ))}
                </ul>
              )}

              {uploading && (
                <p role="status" className="mt-2 text-sm">
                  {uploadProgress} von {files.length} verarbeitet
                </p>
              )}
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
              disabled={uploading || files.length === 0}
              className="w-full rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {uploading
                ? "Wird hochgeladen..."
                : `Alle hochladen (${files.length})`}
            </button>
          </form>
        </section>}

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold">Dokumentenübersicht</h2>
              <p className="mt-1 text-sm text-slate-500">{filteredDocuments.length} von {documents.length} Dokumenten</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input type="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Dateiname, Unternehmen, Fall suchen..." aria-label="Dokumente suchen" className="input w-full sm:w-72" />
              <select aria-label="Fall filtern" value={caseFilter} onChange={(event) => { setCaseFilter(event.target.value); setPage(1); }} className="input max-w-56">
                <option value="all">Alle Fälle</option>
                <option value="none">Ohne Fall</option>
                {cases.map((item) => <option key={item.id} value={item.id}>{getCaseLabel(item)}</option>)}
              </select>
              <select aria-label="Status filtern" value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }} className="input max-w-48">
                <option value="all">Alle Status</option>
                <option value="ready">bereit</option>
                <option value="partial">Teilweise verarbeitet</option>
                <option value="pending">Ausstehend</option>
                <option value="failed">Fehler</option>
              </select>
            </div>
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
              {visibleDocuments.map((item) => {
                const isBusy = busyDocumentId === item.id;

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
                          {formatFileSize(item.file_size)} ·
                          Hochgeladen von{" "}
                          {item.uploaded_by ?? "Unbekannt"}
                        </p>

                        <p className="mt-2 text-xs font-medium text-slate-500">
                          Verarbeitung: {item.processing_status} ·
                          Embedding: {item.embedding_status}
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

                        <button
                          type="button"
                          onClick={() => void toggleRoutingHistory(item.id)}
                          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50"
                        >
                          {historyDocumentId === item.id ? "Verlauf schließen" : "KI-Zuordnungsverlauf"}
                        </button>

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

                    {historyDocumentId === item.id && (
                      <section className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-4" aria-label="Fallzuordnungsverlauf">
                        <h3 className="text-sm font-semibold">Fallzuordnungen und KI-Vorschläge</h3>
                        {historyLoading ? <p className="mt-2 text-sm">Lade Verlauf…</p> : routingHistory.length === 0 ? (
                          <p className="mt-2 text-sm text-slate-500">Noch keine protokollierten Entscheidungen.</p>
                        ) : (
                          <ul className="mt-3 space-y-3">
                            {routingHistory.map((event) => (
                              <li key={event.id} className="rounded-lg bg-white p-3 text-sm">
                                <p className="font-medium">{event.event_type === "suggestion" ? "KI-Vorschlag" : event.event_type === "correction" ? "Manuelle Korrektur" : "Bestätigte Zuordnung"} · {event.decision}</p>
                                <p className="text-xs text-slate-500">{event.created_at ? new Date(event.created_at).toLocaleString("de-DE") : "Datum unbekannt"}</p>
                                {event.reason && <p className="mt-1">{event.reason}</p>}
                                {event.confidence != null && <p className="mt-1 text-slate-600">KI-Konfidenz: {Math.round(event.confidence * 100)} %</p>}
                                {event.assigned_case_id != null && <p className="mt-1">Zugeordneter Fall: #{event.assigned_case_id}</p>}
                                {event.event_type === "correction" && <p className="mt-1 text-slate-600">Vorheriger Fall: {event.details?.previous_case_id ?? "ohne Zuordnung"}</p>}
                                {event.details?.candidates && event.details.candidates.length > 0 && (
                                  <details className="mt-2"><summary className="cursor-pointer text-violet-700">Verglichene Kandidaten</summary>
                                    <ul className="mt-1 list-disc pl-5">{event.details.candidates.map((candidate) => <li key={candidate.case_id}>{candidate.title} (#{candidate.case_id}) — {candidate.similarity == null ? "–" : candidate.similarity.toFixed(3)}</li>)}</ul>
                                  </details>
                                )}
                              </li>
                            ))}
                          </ul>
                        )}
                      </section>
                    )}

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
                            {getCaseLabel(caseItem)}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {!loading && filteredDocuments.length > 0 && (
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-5 text-sm">
              <div className="flex items-center gap-3 text-slate-500">
                <span>{(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, filteredDocuments.length)} von {filteredDocuments.length}</span>
                <select aria-label="Dokumente pro Seite" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }} className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-slate-700">
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <button type="button" disabled={currentPage <= 1} onClick={() => setPage(1)} className="rounded-lg border border-slate-200 px-3 py-2 disabled:opacity-40">«</button>
                <button type="button" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)} className="rounded-lg border border-slate-200 px-3 py-2 disabled:opacity-40">Zurück</button>
                <span className="px-2 text-slate-600">Seite {currentPage} / {totalPages}</span>
                <button type="button" disabled={currentPage >= totalPages} onClick={() => setPage(currentPage + 1)} className="rounded-lg border border-slate-200 px-3 py-2 disabled:opacity-40">Weiter</button>
                <button type="button" disabled={currentPage >= totalPages} onClick={() => setPage(totalPages)} className="rounded-lg border border-slate-200 px-3 py-2 disabled:opacity-40">»</button>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
