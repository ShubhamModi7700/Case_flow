import type { HistoryItem } from "../../types";
import { formatDateTime } from "./formatters";

export default function HistoryTab({ history }: { history: HistoryItem[] }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">Fallverlauf</h2>
      {history.length === 0 ? (
        <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Keine Verlaufseinträge vorhanden.</p>
      ) : (
        <div className="mt-6 space-y-6">
          {history.map((entry) => (
            <div key={entry.id} className="relative border-l-2 border-slate-200 pl-6">
              <div className="absolute -left-[7px] top-1 h-3 w-3 rounded-full bg-slate-950" />
              <p className="font-semibold text-slate-950">{entry.change}</p>
              {entry.note && <p className="mt-2 text-sm text-slate-600">{entry.note}</p>}
              <p className="mt-2 text-xs text-slate-400">{formatDateTime(entry.created_at)} · {entry.responsible_person ?? "System"}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
