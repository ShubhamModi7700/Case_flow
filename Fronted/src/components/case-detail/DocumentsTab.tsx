import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api";
import type { DocumentItem } from "../../types";

type DocumentsTabProps = {
  documents: DocumentItem[];
  reload: () => Promise<void>;
  isManager: boolean;
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
  documents,
  reload,
  isManager,
}: DocumentsTabProps) {
  const [deletingId, setDeletingId] =
    useState<number | null>(null);

  const [error, setError] = useState("");

  async function downloadDocument(
    documentId: number,
  ): Promise<void> {
    try {
      setError("");

      const response =
        await api.get<{
          download_url: string;
        }>(
          `/documents/${documentId}/download`,
        );

      window.open(
        response.data.download_url,
        "_blank",
        "noopener,noreferrer",
      );
    } catch (requestError) {
      console.error(
        "Dokument konnte nicht heruntergeladen werden:",
        requestError,
      );

      setError(
        "Das Dokument konnte nicht heruntergeladen werden.",
      );
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

      await api.delete(
        `/documents/${documentId}`,
      );

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
            Die diesem Fall zugeordneten Dokumente
            werden auf der zentralen Dokumentenseite
            verwaltet.
          </p>
        </div>

        <Link
          to="/documents"
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          Dokumente öffnen
        </Link>
      </div>

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
            const isDeleting =
              deletingId === document.id;

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
                    {formatFileSize(
                      document.file_size,
                    )}

                    {document.uploaded_by
                      ? ` · Hochgeladen von ${document.uploaded_by}`
                      : ""}

                    {document.uploaded_at
                      ? ` · ${formatDate(
                          document.uploaded_at,
                        )}`
                      : ""}
                  </p>
                </div>

                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      void downloadDocument(
                        document.id,
                      )
                    }
                    className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Herunterladen
                  </button>

                  {isManager && (
                    <button
                      type="button"
                      disabled={isDeleting}
                      onClick={() =>
                        void deleteDocument(
                          document.id,
                        )
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