interface DeleteCaseModalProps {
  caseTitle: string;
  deleting: boolean;
  error: string;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}

export default function DeleteCaseModal({
  caseTitle,
  deleting,
  error,
  onCancel,
  onConfirm,
}: DeleteCaseModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-case-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !deleting) {
          onCancel();
        }
      }}
    >
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
        <h2
          id="delete-case-title"
          className="text-xl font-semibold text-slate-950"
        >
          Fall löschen
        </h2>

        <p className="mt-4 text-sm leading-6 text-slate-600">
          Möchten Sie den Fall <strong>„{caseTitle}“</strong> wirklich
          entfernen? Der Fall wird archiviert und erscheint danach nicht mehr
          in den aktiven Falllisten.
        </p>

        <p className="mt-3 text-sm font-medium text-amber-800">
          Die zugehörigen Daten bleiben für Nachvollziehbarkeit erhalten.
        </p>

        {error && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={deleting}
            className="rounded-xl border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Abbrechen
          </button>

          <button
            type="button"
            onClick={() => void onConfirm()}
            disabled={deleting}
            className="rounded-xl bg-red-700 px-5 py-3 text-sm font-semibold text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {deleting ? "Wird gelöscht..." : "Fall löschen"}
          </button>
        </div>
      </div>
    </div>
  );
}
