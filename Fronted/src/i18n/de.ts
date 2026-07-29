export const statusLabels: Record<string, string> = {
  New: "Neu",
  "Under Review": "In Prüfung",
  "In Progress": "In Bearbeitung",
  Waiting: "Wartend",
  Completed: "Abgeschlossen",
  Critical: "Kritisch",
};

export const riskLabels: Record<string, string> = {
  Low: "Niedrig",
  Medium: "Mittel",
  High: "Hoch",
};

export const categoryLabels: Record<string, string> = {
  Customer: "Kunde",
  Contract: "Vertrag",
  Supplier: "Lieferant",
  Employee: "Mitarbeiter",
  Project: "Projekt",
  Other: "Sonstiges",
};

export function translateStatus(value: string): string {
  return statusLabels[value] ?? value;
}

export function translateRisk(value: string): string {
  return riskLabels[value] ?? value;
}
