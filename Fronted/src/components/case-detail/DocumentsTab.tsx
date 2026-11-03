
import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api";
import type { DocumentItem } from "../../types";

type DocumentsTabProps = {
  caseId: number;
  documents: DocumentItem[];
  reload: () => Promise<void>;
  canEdit: boolean;
  isManager: boolean;
  onOpenAI: () => void;
};

function formatFileSize(size: number): string {
  if (size <= 0) {
    return "Unbekannte Größe";
  }

  if (size < 1024) {
    return `${size} B`;
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("de-DE");
}

export default function DocumentsTab({
  caseId,
  documents,
  reload,
  canEdit,
  isManager,
  onOpenAI,
}: DocumentsTabProps) {
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [openingId, setOpeningId] = useState<number | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [completedCount, setCompletedCount] = useState(0);
  const [uploadResults, setUploadResults] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function uploadAll(): Promise<void> {
    if (uploading || selectedFiles.length === 0) return;
    setUploading(true);
    setCompletedCount(0);
    setError("");
    setUploadResults([]);
    const failed: File[] = [];
    const results: string[] = [];
    let successCount = 0;
    try {
      // Each file uses the existing case-specific endpoint and its access checks.
      // Continue with remaining files even when one upload fails.
      for (const file of selectedFiles) {
        try {
          const form = new FormData();
          form.append("file", file);
          await api.post(`/cases/${caseId}/documents`, form);
          successCount += 1;
          results.push(`✓ ${file.name}`);
        } catch (uploadError) {
          console.error("Dokument-Upload fehlgeschlagen:", file.name, uploadError);
          failed.push(file);
          results.push(`✗ ${file.name} – Upload fehlgeschlagen`);
        }
        setCompletedCount(results.length);
        setUploadResults([...results]);
      }
      setSelectedFiles(failed);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (successCount > 0) await reload();
      if (failed.length > 0) {
        setError(`${failed.length} von ${results.length} Dokumenten konnten nicht hochgeladen werden. Fehlgeschlagene Dateien können erneut hochgeladen werden.`);
      }
    } catch (refreshError) {
      console.error("Dokumentenliste konnte nicht aktualisiert werden:", refreshError);
      setError("Die Dokumentenliste konnte nicht aktualisiert werden. Bitte laden Sie die Seite neu.");
    } finally {
      setUploading(false);
    }
  }

  // Preserve the existing AI navigation callback.
  void onOpenAI;

  async function openDocument(
    document: DocumentItem,
  ): Promise<void> {
    // Open the tab before the async request to avoid popup blocking.
    const previewWindow = window.open("", "_blank");

    if (!previewWindow) {
      setError(
        "Bitte erlauben Sie Pop-ups für Case Flow.",
      );
      return;
    }

    try {
      setOpeningId(document.id);
      setError("");

      const response = await api.get<Blob>(
        `/documents/${document.id}/preview`,
        {
          responseType: "blob",
        },
      );

      // Compatible with Axios versions where headers.get()
      // is not guaranteed to be callable.
      const rawContentType =
        response.headers["content-type"];

      const contentType =
        typeof rawContentType === "string" &&
        rawContentType.length > 0
          ? rawContentType
          : "application/octet-stream";

      const blob = new Blob([response.data], {
        type: contentType,
      });

      const previewUrl = URL.createObjectURL(blob);

      previewWindow.opener = null;
      previewWindow.location.replace(previewUrl);

      // Keep the object URL available while the preview tab
      // is open. Release it when the parent page unloads.
      window.addEventListener(
        "pagehide",
        () => URL.revokeObjectURL(previewUrl),
        { once: true },
      );
    } catch (requestError) {
      previewWindow.close();

      console.error(
        "Dokumentvorschau fehlgeschlagen:",
        requestError,
      );

      setError(
        `Die Vorschau für „${document.file_name}“ konnte nicht geöffnet werden.`,
      );
    } finally {
      setOpeningId(null);
    }
  }

  async function downloadDocument(
    document: DocumentItem,
  ): Promise<void> {
    try {
      setDownloadingId(document.id);
      setError("");

      const response = await api.get<{
        download_url: string;
        file_name: string;
        expires_in: number;
      }>(`/documents/${document.id}/download`);

      const anchor = window.document.createElement("a");

      anchor.href = response.data.download_url;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";

      window.document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } catch (requestError) {
      console.error(
        "Dokument konnte nicht heruntergeladen werden:",
        requestError,
      );

      setError(
        `„${document.file_name}“ konnte nicht heruntergeladen werden.`,
      );
    } finally {
      setDownloadingId(null);
    }
  }

  async function deleteDocument(
    documentId: number,
  ): Promise<void> {
    const confirmed = window.confirm(
      "Möchten Sie dieses Dokument wirklich dauerhaft löschen?\n\nDieser Vorgang kann nicht rückgängig gemacht werden.",
    );

    if (!confirmed) {
      return;
    }

    try {
      setDeletingId(documentId);
      setError("");

      await api.delete(`/documents/${documentId}`);

      await reload();
    } catch (requestError) {
      console.error(
        "Dokument konnte nicht gelöscht werden:",
        requestError,
      );

      setError(
        "Das Dokument konnte nicht gelöscht werden.",
      );
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            Dokumente
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Dokumente für diesen Fall hochladen und verwalten.
          </p>
        </div>

        <Link
          to="/documents"
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          Dokumente öffnen
        </Link>
      </div>

      {canEdit && (
        <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <label htmlFor="case-document-files" className="block text-sm font-semibold text-slate-800">
            Mehrere Dokumente auswählen
          </label>
          <input
            id="case-document-files"
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.eml,.msg"
            disabled={uploading}
            onChange={(event) => {
              setSelectedFiles(Array.from(event.target.files ?? []));
              setCompletedCount(0);
              setUploadResults([]);
              setError("");
            }}
            className="mt-2 block w-full text-sm text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-white file:px-4 file:py-2 file:font-semibold"
          />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={uploading || selectedFiles.length === 0}
              onClick={() => void uploadAll()}
              className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {uploading ? "Wird hochgeladen..." : `Alle hochladen (${selectedFiles.length})`}
            </button>
            {uploading && <span role="status" className="text-sm text-slate-600">{completedCount} von {selectedFiles.length} verarbeitet</span>}
          </div>
          {uploadResults.length > 0 && (
            <ul className="mt-3 max-h-36 overflow-y-auto text-xs text-slate-700" aria-label="Upload-Ergebnisse">
              {uploadResults.map((result, index) => <li key={`${index}-${result}`} className="py-0.5">{result}</li>)}
            </ul>
          )}
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {documents.length === 0 ? (
        <div className="mt-6 rounded-xl border border-dashed border-slate-300 p-8 text-center">
          <p className="text-sm text-slate-500">
            Diesem Fall sind noch keine Dokumente
            zugeordnet.
          </p>

          <Link
            to="/documents"
            className="mt-4 inline-block text-sm font-semibold text-slate-700 hover:text-slate-950"
          >
            Zu den Dokumenten
          </Link>
        </div>
      ) : (
        <div className="mt-6 divide-y divide-slate-200">
          {documents.map((document) => {
            const isDeleting = deletingId === document.id;
            const isOpening = openingId === document.id;
            const isDownloading =
              downloadingId === document.id;

            return (
              <article
                key={document.id}
                className="flex flex-wrap items-center justify-between gap-4 py-5 first:pt-0 last:pb-0"
              >
                <div className="min-w-0 flex-1">
                  <h3 className="truncate font-semibold text-slate-950">
                    {document.file_name}
                  </h3>

                  <p className="mt-1 text-sm text-slate-500">
                    {document.description ||
                      "Keine Beschreibung"}
                  </p>

                  <p className="mt-1 text-xs text-slate-400">
                    {formatFileSize(document.file_size)}

                    {document.uploaded_by
                      ? ` · Hochgeladen von ${document.uploaded_by}`
                      : ""}

                    {document.uploaded_at
                      ? ` · ${formatDate(document.uploaded_at)}`
                      : ""}
                  </p>

                  <p className="mt-2 text-xs font-medium text-slate-500">
                    Verarbeitung: {document.processing_status}
                    {" · "}
                    Embedding: {document.embedding_status}

                    {document.chunk_count > 0
                      ? ` · ${document.chunk_count} Textabschnitte`
                      : ""}
                  </p>

                  {document.processing_error && (
                    <p className="mt-1 text-xs text-red-600">
                      {document.processing_error}
                    </p>
                  )}
                </div>

                <div className="flex shrink-0 flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={isOpening}
                    onClick={() => void openDocument(document)}
                    className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isOpening
                      ? "Wird geöffnet..."
                      : "Öffnen"}
                  </button>

                  <button
                    type="button"
                    disabled={isDownloading}
                    onClick={() =>
                      void downloadDocument(document)
                    }
                    className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isDownloading
                      ? "Wird heruntergeladen..."
                      : "Herunterladen"}
                  </button>

                  {isManager && (
                    <button
                      type="button"
                      disabled={isDeleting}
                      onClick={() =>
                        void deleteDocument(document.id)
                      }
                      className="rounded-xl border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isDeleting
                        ? "Wird gelöscht..."
                        : "Löschen"}
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
