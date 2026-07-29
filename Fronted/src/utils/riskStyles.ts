export type RiskValue = "Low" | "Medium" | "High";

export const riskConfig: Record<RiskValue, {
  label: string;
  badgeClass: string;
  selectClass: string;
  cardClass: string;
  textClass: string;
}> = {
  Low: {
    label: "Niedrig",
    badgeClass: "border border-green-200 bg-green-100 text-green-700",
    selectClass: "border-green-300 bg-green-50 text-green-800 focus:border-green-500 focus:ring-green-200",
    cardClass: "border-green-200 bg-green-50",
    textClass: "text-green-700",
  },
  Medium: {
    label: "Mittel",
    badgeClass: "border border-amber-200 bg-amber-100 text-amber-700",
    selectClass: "border-amber-300 bg-amber-50 text-amber-800 focus:border-amber-500 focus:ring-amber-200",
    cardClass: "border-amber-200 bg-amber-50",
    textClass: "text-amber-700",
  },
  High: {
    label: "Hoch",
    badgeClass: "border border-red-200 bg-red-100 text-red-700",
    selectClass: "border-red-300 bg-red-50 text-red-800 focus:border-red-500 focus:ring-red-200",
    cardClass: "border-red-200 bg-red-50",
    textClass: "text-red-700",
  },
};

export function getRiskConfig(value: string) {
  return riskConfig[value as RiskValue] ?? {
    label: value,
    badgeClass: "border border-slate-200 bg-slate-100 text-slate-700",
    selectClass: "border-slate-300 bg-white text-slate-800",
    cardClass: "border-slate-200 bg-white",
    textClass: "text-slate-700",
  };
}
