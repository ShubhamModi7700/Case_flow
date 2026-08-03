import { useState } from "react";

import type {
  CaseCategory,
  CaseItem,
  CaseStatus,
  RiskLevel,
} from "../../types";
import { getRiskConfig } from "../../utils/riskStyles";
import Field from "./Field";
import type { CaseUpdatePayload } from "./types";

interface EditCaseModalProps {
  caseItem: CaseItem;
  saving: boolean;
  error: string;
  onCancel: () => void;
  onSave: (values: CaseUpdatePayload) => Promise<void>;
}

export default function EditCaseModal({
  caseItem,
  saving,
  error,
  onCancel,
  onSave,
}: EditCaseModalProps) {
  const [title, setTitle] = useState(caseItem.title);
  const [company, setCompany] = useState(caseItem.company);
  const [category, setCategory] = useState<CaseCategory>(caseItem.category);
  const [department, setDepartment] = useState(caseItem.department ?? "");
  const [externalContact, setExternalContact] = useState(
    caseItem.external_contact ?? "",
  );
  const [responsiblePerson, setResponsiblePerson] = useState(
    caseItem.responsible_person ?? "",
  );
  const [status, setStatus] = useState<CaseStatus>(caseItem.status);
  const [risk, setRisk] = useState<RiskLevel>(caseItem.risk);
  const [riskReason, setRiskReason] = useState(caseItem.risk_reason ?? "");
  const [managementSummary, setManagementSummary] = useState(
    caseItem.management_summary ?? "",
  );
  const [localError, setLocalError] = useState("");
  const [description, setDescription] = useState(caseItem.description ?? "");
  const [nextAction, setNextAction] = useState(caseItem.next_action ?? "");
  const [primaryDeadline, setPrimaryDeadline] = useState(
    caseItem.primary_deadline ?? "",
  );
  const [followUpDate, setFollowUpDate] = useState(
    caseItem.follow_up_date ?? "",
  );

  async function submitForm(
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    const normalizedTitle = title.trim();
    const normalizedCompany = company.trim();
    if (!normalizedTitle || !normalizedCompany) return;

    if (risk !== "Low" && !riskReason.trim()) {
      setLocalError(
        "Bitte geben Sie eine Begründung für ein mittleres oder hohes Risiko ein.",
      );
      return;
    }

    setLocalError("");

    await onSave({
      title: normalizedTitle,
      company: normalizedCompany,
      department: department.trim() || null,
      category,
      external_contact: externalContact.trim() || null,
      responsible_person: responsiblePerson.trim() || null,
      status,
      risk,
      risk_reason: riskReason.trim() || null,
      risk_is_manual: true,
      management_summary: managementSummary.trim() || null,
      description: description.trim() || null,
      next_action: nextAction.trim() || null,
      primary_deadline: primaryDeadline || null,
      follow_up_date: followUpDate || null,
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-case-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !saving) {
          onCancel();
        }
      }}
    >
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between gap-4">
          <h2
            id="edit-case-title"
            className="text-xl font-semibold text-slate-950"
          >
            Fall bearbeiten
          </h2>

          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="rounded-lg px-3 py-2 text-sm font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-950 disabled:opacity-50"
          >
            Schließen
          </button>
        </div>

        {(error || localError) && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {localError || error}
          </div>
        )}

        <form
          onSubmit={submitForm}
          className="mt-6 grid gap-4 sm:grid-cols-2"
        >
          <Field label="Titel" className="sm:col-span-2">
            <input
              required
              minLength={3}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Unternehmen" className="sm:col-span-2">
            <input
              required
              value={company}
              onChange={(event) => setCompany(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Abteilung">
            <input
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Kategorie">
            <select
              value={category}
              onChange={(event) =>
                setCategory(event.target.value as CaseCategory)
              }
              className="input"
            >
              <option value="Customer">Kunde</option>
              <option value="Contract">Vertrag</option>
              <option value="Supplier">Lieferant</option>
              <option value="Employee">Mitarbeiter</option>
              <option value="Project">Projekt</option>
              <option value="Other">Sonstiges</option>
            </select>
          </Field>

          <Field label="Status">
            <select
              value={status}
              onChange={(event) =>
                setStatus(event.target.value as CaseStatus)
              }
              className="input"
            >
              <option value="New">Neu</option>
              <option value="Under Review">In Prüfung</option>
              <option value="In Progress">In Bearbeitung</option>
              <option value="Waiting">Wartend</option>
              <option value="Completed">Abgeschlossen</option>
              <option value="Critical">Kritisch</option>
            </select>
          </Field>

          <Field label="Risiko">
            <select
              value={risk}
              onChange={(event) =>
                setRisk(event.target.value as RiskLevel)
              }
              className={`input font-semibold transition-colors ${getRiskConfig(risk).selectClass}`}
            >
              <option value="Low">Niedrig</option>
              <option value="Medium">Mittel</option>
              <option value="High">Hoch</option>
            </select>
          </Field>

          <Field label="Risikobegründung" className="sm:col-span-2">
            <textarea
              value={riskReason}
              onChange={(event) => setRiskReason(event.target.value)}
              rows={3}
              placeholder="Warum wurde diese Risikostufe gewählt?"
              className="input"
            />
          </Field>

          <Field label="Verantwortliche Person">
            <input
              value={responsiblePerson}
              onChange={(event) => setResponsiblePerson(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Externer Kontakt">
            <input
              value={externalContact}
              onChange={(event) => setExternalContact(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Hauptfrist">
            <input
              type="date"
              value={primaryDeadline}
              onChange={(event) => setPrimaryDeadline(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Wiedervorlage">
            <input
              type="date"
              value={followUpDate}
              onChange={(event) => setFollowUpDate(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Management-Zusammenfassung" className="sm:col-span-2">
            <textarea
              value={managementSummary}
              onChange={(event) => setManagementSummary(event.target.value)}
              rows={4}
              placeholder="Kurze Zusammenfassung für das Management"
              className="input"
            />
          </Field>

          <Field label="Nächste Maßnahme" className="sm:col-span-2">
            <textarea
              value={nextAction}
              onChange={(event) => setNextAction(event.target.value)}
              rows={3}
              className="input"
            />
          </Field>

          <Field label="Beschreibung" className="sm:col-span-2">
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={4}
              className="input"
            />
          </Field>

          <div className="flex justify-end gap-3 sm:col-span-2">
            <button
              type="button"
              onClick={onCancel}
              disabled={saving}
              className="rounded-xl border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              Abbrechen
            </button>

            <button
              type="submit"
              disabled={saving || !title.trim() || !company.trim()}
              className="rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Wird gespeichert..." : "Änderungen speichern"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
