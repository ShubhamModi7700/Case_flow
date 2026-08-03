import type {
  CaseStatus,
  RiskLevel,
} from "../../types";

const statusLabels: Record<CaseStatus, string> = {
  New: "Neu",
  "Under Review": "In Prüfung",
  "In Progress": "In Bearbeitung",
  Waiting: "Wartend",
  Completed: "Abgeschlossen",
  Critical: "Kritisch",
};

const riskLabels: Record<RiskLevel, string> = {
  Low: "Niedrig",
  Medium: "Mittel",
  High: "Hoch",
};

export function StatusBadge({
  value,
}: {
  value: CaseStatus;
}) {
  return (
    <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold text-slate-700">
      {statusLabels[value]}
    </span>
  );
}

export function RiskBadge({
  value,
}: {
  value: RiskLevel;
}) {
  return (
    <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-semibold text-slate-700">
      {riskLabels[value]}
    </span>
  );
}