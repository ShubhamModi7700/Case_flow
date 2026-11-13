import axios from "axios";
import { api } from "../api";

/** Retry only transient transport failures; never retry authorization or validation errors. */
export function isTransientUploadError(error: unknown): boolean {
  if (!axios.isAxiosError(error)) return false;
  const status = error.response?.status;
  return status === 408 || status === 429 || (status !== undefined && status >= 500) ||
    (status === undefined && ["ECONNABORTED", "ETIMEDOUT", "ERR_NETWORK"].includes(error.code ?? ""));
}

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export async function uploadDirectFile(
  file: File,
  options: { batchItemId: string; caseId: number | null; description?: string | null },
): Promise<unknown> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const init = await api.post<{ upload_url: string; upload_token: string }>(
        "/documents/upload-init",
        {
          filename: file.name,
          batch_item_id: options.batchItemId,
          file_size: file.size,
          content_type: file.type || "application/octet-stream",
          case_id: options.caseId,
          description: options.description ?? null,
        },
      );
      // Direct-to-storage upload: never send file bytes through Vercel Functions.
      await axios.put(init.data.upload_url, file, {
        headers: { "Content-Type": file.type || "application/octet-stream" },
        timeout: 180000,
      });
      // Retry completion with the SAME token; the backend deduplicates by path.
      for (let completionAttempt = 0; completionAttempt < 3; completionAttempt++) {
        try {
          const response = await api.post("/documents/upload-complete", {
            upload_token: init.data.upload_token,
          });
          return response.data;
        } catch (error) {
          if (!isTransientUploadError(error) || completionAttempt === 2) throw error;
          await delay(600 * 2 ** completionAttempt);
        }
      }
    } catch (error) {
      lastError = error;
      if (!isTransientUploadError(error) || attempt === 2) throw error;
      await delay(800 * 2 ** attempt + Math.floor(Math.random() * 250));
    }
  }
  throw lastError ?? new Error("Upload fehlgeschlagen");
}
