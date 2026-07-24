import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import type { CaseItem, DocumentItem } from "../types";
import { formatFileSize } from "../utils/fileHelpers";

type DocumentDownloadResponse = {
  download_url: string;
  file_name: string;
  expires_in: number;
};

function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export default function DocumentsPage() {
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

  async function loadData(): Promise<void> {
    try {
      setLoading(true);
      setError("");
      const [caseResponse, documentResponse] = await Promise.all([
        api.get<CaseItem[]>("/cases"),
        api.get<DocumentItem[]>("/documents"),
      ]);
      setCases(caseResponse.data.filter((item) => !item.is_archived));
      setDocuments(documentResponse.data);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "The documents could not be loaded."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  async function uploadDocument(event: React.FormEvent<HTMLFormElement>) {
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
      if (description.trim()) formData.append("description", description.trim());
      if (selectedCaseId) formData.append("case_id", selectedCaseId);

      await api.post("/documents", formData);
      setFile(null);
      setDescription("");
      setSelectedCaseId("");
      const input = document.getElementById("document-page-file") as HTMLInputElement | null;
      if (input) input.value = "";
      await loadData();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "The document could not be uploaded."));
    } finally {
      setUploading(false);
    }
  }

  async function assignCase(documentId: number, caseId: string): Promise<void> {
    try {
      setBusyDocumentId(documentId);
      setError("");
      await api.patch(`/documents/${documentId}/case`, {
        case_id: caseId ? Number(caseId) : null,
      });
      await loadData();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "The document assignment could not be changed."));
    } finally {
      setBusyDocumentId(null);
    }
  }

  async function downloadDocument(documentId: number): Promise<void> {
    try {
      setBusyDocumentId(documentId);
      const response = await api.get<DocumentDownloadResponse>(
        `/documents/${documentId}/download`,
      );
      window.location.assign(response.data.download_url);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "The document could not be downloaded."));
    } finally {
      setBusyDocumentId(null);
    }
  }

  async function deleteDocument(documentId: number): Promise<void> {
    if (!window.confirm("Delete this document permanently from Supabase Storage?")) return;
    try {
      setBusyDocumentId(documentId);
      await api.delete(`/documents/${documentId}`);
      await loadData();
    } catch (requestError) {
      setError(getErrorMessage(requestError, "The document could not be deleted."));
    } finally {
      setBusyDocumentId(null);
    }
  }

  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return documents;
    return documents.filter((item) =>
      [item.file_name, item.description, item.uploaded_by, item.company, item.department]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query)),
    );
  }, [documents, search]);

  return (
    <div className="mx-auto max-w-7xl px-8 py-8">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Case Flow</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-950">Documents</h1>
        <p className="mt-2 text-sm text-slate-500">
          Upload and manage documents.
        </p>
      </header>

      {error && (
        <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}

      <div className="mt-8 grid gap-6 xl:grid-cols-[380px_1fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold">Upload document</h2>
          <p className="mt-2 text-sm text-slate-500">
            Maximum file size: 10 MB.
          </p>

          <form onSubmit={uploadDocument} className="mt-5 space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium">Link to case (optional)</label>
              <select value={selectedCaseId} onChange={(event) => setSelectedCaseId(event.target.value)} className="input">
                <option value="">No linked case</option>
                {cases.map((item) => (
                  <option key={item.id} value={item.id}>
                    #{item.id} — {item.company}{item.department ? ` / ${item.department}` : ""}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">File</label>
              <input
                id="document-page-file"
                type="file"
                required
                accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.csv,.txt,.png,.jpg,.jpeg"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                className="input"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">Description</label>
              <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} className="input" />
            </div>

            <button type="submit" disabled={uploading} className="w-full rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">
              {uploading ? "Uploading..." : "Upload document"}
            </button>
          </form>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold">All documents</h2>
              <p className="mt-1 text-sm text-slate-500">{documents.length} document(s)</p>
            </div>
            <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search documents..." className="input max-w-xs" />
          </div>

          {loading ? (
            <p className="mt-6 text-sm text-slate-500">Loading documents...</p>
          ) : filteredDocuments.length === 0 ? (
            <p className="mt-6 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">No documents found.</p>
          ) : (
            <div className="mt-6 divide-y divide-slate-100">
              {filteredDocuments.map((item) => {
                const isBusy = busyDocumentId === item.id;
                return (
                  <div key={item.id} className="py-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="break-all font-medium text-slate-950">{item.file_name}</p>
                        <p className="mt-1 text-sm text-slate-500">{item.description ?? "No description"}</p>
                        <p className="mt-1 text-xs text-slate-400">
                          {formatFileSize(item.file_size)} · Uploaded by {item.uploaded_by ?? "Unknown"}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        {item.case_id && (
                          <Link to={`/cases/${item.case_id}`} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50">Open case</Link>
                        )}
                        <button type="button" disabled={isBusy} onClick={() => void downloadDocument(item.id)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50">Download</button>
                        <button type="button" disabled={isBusy} onClick={() => void deleteDocument(item.id)} className="rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50">Delete</button>
                      </div>
                    </div>
                    <div className="mt-3 max-w-md">
                      <label className="mb-1 block text-xs font-medium text-slate-500">Linked case</label>
                      <select
                        value={item.case_id ?? ""}
                        disabled={isBusy}
                        onChange={(event) => void assignCase(item.id, event.target.value)}
                        className="input"
                      >
                        <option value="">No linked case</option>
                        {cases.map((caseItem) => (
                          <option key={caseItem.id} value={caseItem.id}>
                            #{caseItem.id} — {caseItem.company}{caseItem.department ? ` / ${caseItem.department}` : ""}
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