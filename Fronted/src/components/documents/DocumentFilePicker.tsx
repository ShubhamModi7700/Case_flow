import { useId, useRef, useState } from "react";

import { formatFileSize } from "../../utils/fileHelpers";

import { UPLOAD_ACCEPT, validateUploadFile } from "../../utils/uploadPolicy";

type DocumentFilePickerProps = {
  file: File | null;
  onFileChange: (file: File | null) => void;
  disabled?: boolean;
  onError?: (message: string) => void;
};

export default function DocumentFilePicker({
  file,
  onFileChange,
  disabled = false,
  onError,
}: DocumentFilePickerProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function selectFile(nextFile: File | null): void {
    if (!nextFile) {
      onError?.("");
      onFileChange(null);
      return;
    }

    const validationError = validateUploadFile(nextFile);
    if (validationError) {
      onFileChange(null);
      if (inputRef.current) inputRef.current.value = "";
      onError?.(validationError);
      return;
    }

    onError?.("");
    onFileChange(nextFile);
  }

  function clearFile(): void {
    onFileChange(null);
    onError?.("");

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  return (
    <div>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={UPLOAD_ACCEPT}
        disabled={disabled}
        onChange={(event) =>
          selectFile(
            event.target.files?.[0] ?? null,
          )
        }
        className="sr-only"
      />

      <div
        onDragEnter={(event) => {
          event.preventDefault();

          if (!disabled) {
            setDragging(true);
          }
        }}
        onDragOver={(event) => {
          event.preventDefault();
        }}
        onDragLeave={(event) => {
          event.preventDefault();
          setDragging(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);

          if (!disabled) {
            selectFile(
              event.dataTransfer.files?.[0] ??
                null,
            );
          }
        }}
        className={`rounded-xl border-2 border-dashed p-5 text-center transition ${
          dragging
            ? "border-slate-500 bg-slate-100"
            : "border-slate-300 bg-slate-50"
        }`}
      >
        {file ? (
          <div className="space-y-3">
            <div>
              <p className="break-all text-sm font-semibold text-slate-900">
                {file.name}
              </p>

              <p className="mt-1 text-xs text-slate-500">
                {formatFileSize(file.size)}
              </p>
            </div>

            <div className="flex justify-center gap-2">
              <label
                htmlFor={inputId}
                className="cursor-pointer rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50"
              >
                Dokument ändern
              </label>

              <button
                type="button"
                onClick={clearFile}
                disabled={disabled}
                className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
              >
                Entfernen
              </button>
            </div>
          </div>
        ) : (
          <div>
            <p className="text-sm font-medium text-slate-700">
              Dokument hierher ziehen und ablegen
            </p>

            <p className="my-2 text-xs text-slate-400">
              oder
            </p>

            <label
              htmlFor={inputId}
              className={`inline-flex rounded-lg bg-slate-950 px-4 py-2 text-sm font-semibold text-white ${
                disabled
                  ? "cursor-not-allowed opacity-50"
                  : "cursor-pointer"
              }`}
            >
              Dokument auswählen
            </label>

            <p className="mt-3 text-xs text-slate-400">
              PDF, Word, Excel oder E-Mail · maximal 10 MB
            </p>

            <p className="mt-1 text-xs text-slate-400">
              Unterstützte Formate: .pdf, .doc, .docx, .xls,
              .xlsx, .eml, .msg
            </p>
          </div>
        )}
      </div>
    </div>
  );
}