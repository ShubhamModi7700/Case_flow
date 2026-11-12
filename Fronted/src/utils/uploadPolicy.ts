/** Defaults mirror GET /documents/upload-policy; update both when changing policy. */
export const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;
export const UPLOAD_EXTENSIONS = [".pdf", ".docx", ".xlsx", ".eml", ".msg"] as const;
export const UPLOAD_ACCEPT = UPLOAD_EXTENSIONS.join(",");
export const UPLOAD_EXTENSION_SET: ReadonlySet<string> = new Set(UPLOAD_EXTENSIONS);

export function validateUploadFile(file: File): string | null {
  const dot = file.name.lastIndexOf(".");
  const extension = dot < 0 ? "" : file.name.slice(dot).toLowerCase();
  if (!UPLOAD_EXTENSION_SET.has(extension)) {
    return "Nicht unterstütztes Format (PDF, DOCX, XLSX, EML oder MSG).";
  }
  if (file.size === 0) return "Die Datei ist leer.";
  if (file.size > MAX_UPLOAD_BYTES) return "Die Datei überschreitet 100 MB.";
  return null;
}
