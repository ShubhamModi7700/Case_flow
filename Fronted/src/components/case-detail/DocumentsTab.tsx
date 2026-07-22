import { useState } from "react";
import { api } from "../../api";
import type { DocumentItem } from "../../types";
import Field from "./Field";
import { formatDateTime } from "./formatters";

export default function DocumentsTab({ caseId, documents, reload }: { caseId: number; documents: DocumentItem[]; reload: () => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [uploadedBy, setUploadedBy] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const apiBaseUrl = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

  async function uploadDocument(event: React.FormEvent<HTMLFormElement>): Promise<void> {
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
      if (uploadedBy.trim()) formData.append("uploaded_by", uploadedBy.trim());

      await api.post(`/cases/${caseId}/documents`, formData);
      setFile(null);
      setDescription("");
      setUploadedBy("");

      const fileInput = document.getElementById("case-document-file") as HTMLInputElement | null;
      if (fileInput) fileInput.value = "";
      await reload();
    } catch (requestError) {
      console.error(requestError);
      setError("The document could not be uploaded.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Upload document</h2>
        {error && <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        <form onSubmit={uploadDocument} className="mt-5 space-y-4">
          <Field label="File"><input id="case-document-file" type="file" required onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="input" /></Field>
          <Field label="Description"><textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} className="input" /></Field>
          <Field label="Uploaded by"><input value={uploadedBy} onChange={(event) => setUploadedBy(event.target.value)} className="input" /></Field>
          <button type="submit" disabled={uploading} className="w-full rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">{uploading ? "Uploading..." : "Upload document"}</button>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold">Documents</h2>
        {documents.length === 0 ? (
          <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">No documents have been uploaded.</p>
        ) : (
          <div className="mt-5 divide-y divide-slate-100">
            {documents.map((item) => (
              <div key={item.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
                <div>
                  <p className="font-medium text-slate-950">{item.file_name}</p>
                  <p className="mt-1 text-sm text-slate-500">{item.description ?? "No description"}</p>
                  <p className="mt-1 text-xs text-slate-400">Uploaded by {item.uploaded_by ?? "Unknown"} on {formatDateTime(item.uploaded_at)}</p>
                </div>
                <a href={`${apiBaseUrl}/cases/documents/${item.id}/download`} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50">Download</a>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
