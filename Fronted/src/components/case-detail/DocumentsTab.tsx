import axios from "axios";
import { useState } from "react";

import { api } from "../../api";
import type { DocumentItem } from "../../types";
import { formatFileSize } from "../../utils/fileHelpers";
import DocumentFilePicker from "../documents/DocumentFilePicker";
import Field from "./Field";
import { formatDateTime } from "./formatters";

type DocumentDownloadResponse = {
  download_url: string;
  file_name: string;
  expires_in: number;
};

type DocumentsTabProps = {
  caseId: number;
  documents: DocumentItem[];
  reload: () => Promise<void>;
};

function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export default function DocumentsTab({
  caseId,
  documents,
  reload,
}: DocumentsTabProps) {
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [uploading, setUploading] = useState(false);
  const [busyDocumentId, setBusyDocumentId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function uploadDocument(
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    if (!file) {
      setError("Please select a file.");
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

      await api.post(`/cases/${caseId}/documents`, formData);

      setFile(null);
      setDescription("");

      await reload();
    } catch (requestError) {
      console.error(requestError);
      setError(
        getErrorMessage(requestError, "The document could not be uploaded."),
      );
    } finally {
      setUploading(false);
    }
  }

  async function downloadDocument(documentId: number): Promise<void> {
    try {
      setBusyDocumentId(documentId);
      setError("");

      const response = await api.get<DocumentDownloadResponse>(
        `/documents/${documentId}/download`,
      );

      window.location.assign(response.data.download_url);
    } catch (requestError) {
      console.error(requestError);
      setError(
        getErrorMessage(requestError, "The document could not be downloaded."),
      );
    } finally {
      setBusyDocumentId(null);
    }
  }

  async function removeDocument(documentId: number): Promise<void> {
    const confirmed = window.confirm(
      "Delete this document permanently from Supabase Storage?",
    );
    if (!confirmed) return;

    try {
      setBusyDocumentId(documentId);
      setError("");
      await api.delete(`/documents/${documentId}`);
      await reload();
    } catch (requestError) {
      console.error(requestError);
      setError(
        getErrorMessage(requestError, "The document could not be deleted."),
      );
    } finally {
      setBusyDocumentId(null);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Upload document</h2>
        <p className="mt-2 text-sm text-slate-500">
          Files are stored in the private Supabase Storage bucket. Maximum size:
          10 MB.
        </p>

        {error && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={uploadDocument} className="mt-5 space-y-4">
          <Field label="File">
            <DocumentFilePicker
              file={file}
              onFileChange={setFile}
              disabled={uploading || !file}
              onError={setError}
            />
          </Field>

          <Field label="Description">
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={3}
              className="input"
            />
          </Field>

          <button
            type="submit"
            disabled={uploading}
            className="w-full rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50"
          >
            {uploading ? "Uploading..." : "Upload document"}
          </button>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Documents</h2>

        {documents.length === 0 ? (
          <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">
            No documents have been uploaded.
          </p>
        ) : (
          <div className="mt-5 divide-y divide-slate-100">
            {documents.map((item) => {
              const isBusy = busyDocumentId === item.id;

              return (
                <div
                  key={item.id}
                  className="flex flex-wrap items-center justify-between gap-4 py-4"
                >
                  <div className="min-w-0">
                    <p className="break-all font-medium text-slate-950">
                      {item.file_name}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {item.description ?? "No description"}
                    </p>
                    <p className="mt-1 text-xs text-slate-400">
                      {formatFileSize(item.file_size)} · Uploaded by{" "}
                      {item.uploaded_by ?? "Unknown"} on{" "}
                      {formatDateTime(item.uploaded_at)}
                    </p>
                  </div>

                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => void downloadDocument(item.id)}
                      className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50"
                    >
                      Download
                    </button>
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => void removeDocument(item.id)}
                      className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
