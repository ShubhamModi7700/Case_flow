import { translateStatus } from "../../i18n/de";
import { getRiskConfig } from "../../utils/riskStyles";

export function StatusBadge({ value }: { value: string }) {
  const styles: Record<string, string> = {
    New: "bg-slate-100 text-slate-700",
    "Under Review": "bg-blue-100 text-blue-700",
    "In Progress": "bg-indigo-100 text-indigo-700",
    Waiting: "bg-amber-100 text-amber-700",
    Completed: "bg-green-100 text-green-700",
    Critical: "bg-red-100 text-red-700",
  };

  return (
    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${styles[value] ?? "bg-slate-100 text-slate-700"}`}>
      {translateStatus(value)}
    </span>
  );
}

export function RiskBadge({ value }: { value: string }) {
  const config = getRiskConfig(value);

  return (
    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${config.badgeClass}`}>
      Risiko: {config.label}
    </span>
  );
}
