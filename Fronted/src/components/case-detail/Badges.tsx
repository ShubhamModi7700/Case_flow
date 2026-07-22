export function StatusBadge({ value }: { value: string }) {
  const styles: Record<string, string> = {
    New: "bg-slate-100 text-slate-700",
    "Under Review": "bg-blue-100 text-blue-700",
    "In Progress": "bg-indigo-100 text-indigo-700",
    Waiting: "bg-amber-100 text-amber-700",
    Completed: "bg-green-100 text-green-700",
    Critical: "bg-red-100 text-red-700",
  };

  return <span className={`rounded-full px-3 py-1 text-xs font-semibold ${styles[value] ?? "bg-slate-100 text-slate-700"}`}>{value}</span>;
}

export function RiskBadge({ value }: { value: string }) {
  const styles: Record<string, string> = {
    Low: "bg-green-100 text-green-700",
    Medium: "bg-amber-100 text-amber-700",
    High: "bg-red-100 text-red-700",
  };

  return <span className={`rounded-full px-3 py-1 text-xs font-semibold ${styles[value] ?? "bg-slate-100 text-slate-700"}`}>{value} risk</span>;
}
