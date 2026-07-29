import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api";
import type { DocumentItem } from "../../types";

type DocumentsTabProps = {
  documents: DocumentItem[];
  reload: () => Promise<void>;
};

function formatFileSize(size: number): string {
  if (size <= 0) {
    return "Unknown size";
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

  return date.toLocaleString();
}

export default function DocumentsTab({
  documents,
  reload,
}: DocumentsTabProps) {
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function downloadDocument(documentId: number): Promise<void> {
    try {
      setError("");

      const response = await api.get<{ download_url: string }>(
        `/documents/${documentId}/download`,
      );

      window.open(
        response.data.download_url,
        "_blank",
        "noopener,noreferrer",
      );
    } catch (requestError) {
      console.error("Document download failed:", requestError);
      setError("The document could not be downloaded.");
    }
  }

  async function deleteDocument(documentId: number): Promise<void> {
    const confirmed = window.confirm(
      "Are you sure you want to delete this document?",
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
      console.error("Document deletion failed:", requestError);
      setError("The document could not be deleted.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            Documents
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Documents linked to this case are managed from the main Documents
            page.
          </p>
        </div>

        <Link
          to="/documents"
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          Open Documents
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
            No documents are linked to this case.
          </p>

          <Link
            to="/documents"
            className="mt-4 inline-block text-sm font-semibold text-slate-700 hover:text-slate-950"
          >
            Go to Documents
          </Link>
        </div>
      ) : (
        <div className="mt-6 divide-y divide-slate-200">
          {documents.map((document) => (
            <article
              key={document.id}
              className="flex flex-wrap items-center justify-between gap-4 py-5 first:pt-0 last:pb-0"
            >
              <div className="min-w-0 flex-1">
                <h3 className="truncate font-semibold text-slate-950">
                  {document.file_name}
                </h3>

                <p className="mt-1 text-sm text-slate-500">
                  {document.description || "No description"}
                </p>

                <p className="mt-1 text-xs text-slate-400">
                  {formatFileSize(document.file_size)}
                  {document.uploaded_by
                    ? ` · Uploaded by ${document.uploaded_by}`
                    : ""}
                  {document.uploaded_at
                    ? ` · ${formatDate(document.uploaded_at)}`
                    : ""}
                </p>
              </div>

              <div className="flex shrink-0 gap-2">
                <button
                  type="button"
                  onClick={() => void downloadDocument(document.id)}
                  className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Download
                </button>

                <button
                  type="button"
                  disabled={deletingId === document.id}
                  onClick={() => void deleteDocument(document.id)}
                  className="rounded-xl border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {deletingId === document.id ? "Deleting..." : "Delete"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}