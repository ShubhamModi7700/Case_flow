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

export const timelineLabels: Record<string, string> = {
  Created: "Erstellt",
  CREATED: "Erstellt",

  Completed: "Abgeschlossen",
  COMPLETED: "Abgeschlossen",

  Document: "Dokument",
  DOCUMENT: "Dokument",

  Note: "Notiz",
  NOTE: "Notiz",

  Milestone: "Meilenstein",
  MILESTONE: "Meilenstein",

  "Task deadline": "Aufgabenfrist",
  TASK_DEADLINE: "Aufgabenfrist",

  Task: "Aufgabe",
  TASK: "Aufgabe",

  Archived: "Archiviert",
  ARCHIVED: "Archiviert",

  Update: "Aktualisierung",
  UPDATE: "Aktualisierung",

  AI: "KI-Analyse",
  ai: "KI-Analyse",

  Comment: "Kommentar",
  COMMENT: "Kommentar",
};

export const eventTitleLabels: Record<string, string> = {
  "Primary deadline": "Hauptfrist",
  "Follow-up date": "Wiedervorlagetermin",
  "Case created": "Fall erstellt",
  "The case was created.": "Der Fall wurde erstellt.",

  "check details and complete case":
    "Falldetails prüfen und Fall abschließen",

  "Check details and complete case":
    "Falldetails prüfen und Fall abschließen",

  "Task created": "Aufgabe erstellt",
  "Task completed": "Aufgabe abgeschlossen",
  "Document uploaded": "Dokument hochgeladen",
  "Case updated": "Fall aktualisiert",
  "Case archived": "Fall archiviert",
  "KI-Vorschläge bestätigt": "KI-Vorschläge bestätigt",
  "KI-Vorschläge übernommen": "KI-Vorschläge übernommen",
  "KI-Management Zusammenfassung bestätigt":
    "KI-Management-Zusammenfassung bestätigt",
  "KI-Management-Zusammenfassung bestätigt":
    "KI-Management-Zusammenfassung bestätigt",
};

export const commonLabels = {
  timelineTitle: "Fallzeitleiste",

  timelineDescription:
    "Verlauf, Dokumente, Aufgaben und anstehende Fristen auf einen Blick.",

  addEntry: "Eintrag hinzufügen",
  cancel: "Abbrechen",

  primaryDeadline: "Hauptfrist",
  followUpDate: "Wiedervorlagetermin",

  upcoming: "Bevorstehend",

  caseCreated: "Fall erstellt",
  caseCreatedDescription: "Der Fall wurde erstellt.",

  checkDetails: "Falldetails prüfen und Fall abschließen",

  saveEntry: "Eintrag speichern",
  saving: "Wird gespeichert...",

  noTimelineEvents:
    "Es sind noch keine Zeitleisteneinträge vorhanden.",

  timelineEntryTitlePlaceholder:
    "Titel des Zeitleisteneintrags",

  optionalDetails: "Optionale Details",

  system: "System",
};

export function translateStatus(value: string): string {
  return statusLabels[value] ?? value;
}

export function translateRisk(value: string): string {
  return riskLabels[value] ?? value;
}

export function translateCategory(value: string): string {
  return categoryLabels[value] ?? value;
}

export function translateTimelineType(value: string): string {
  return timelineLabels[value] ?? value;
}

export function translateEventTitle(value: string): string {
  return eventTitleLabels[value] ?? value;
}