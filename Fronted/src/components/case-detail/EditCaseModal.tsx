import { useState } from "react";

import type {
  CaseCategory,
  CaseItem,
  CaseStatus,
  RiskLevel,
} from "../../types";
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
  const [category, setCategory] = useState<CaseCategory>(caseItem.category);
  const [companyDepartment, setCompanyDepartment] = useState(
    caseItem.company_department ?? "",
  );
  const [externalContact, setExternalContact] = useState(
    caseItem.external_contact ?? "",
  );
  const [responsiblePerson, setResponsiblePerson] = useState(
    caseItem.responsible_person ?? "",
  );
  const [status, setStatus] = useState<CaseStatus>(caseItem.status);
  const [risk, setRisk] = useState<RiskLevel>(caseItem.risk);
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
    if (!normalizedTitle) return;

    await onSave({
      title: normalizedTitle,
      category,
      company_department: companyDepartment.trim() || null,
      external_contact: externalContact.trim() || null,
      responsible_person: responsiblePerson.trim() || null,
      status,
      risk,
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
            Edit case
          </h2>

          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="rounded-lg px-3 py-2 text-sm font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-950 disabled:opacity-50"
          >
            Close
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form
          onSubmit={submitForm}
          className="mt-6 grid gap-4 sm:grid-cols-2"
        >
          <Field label="Title" className="sm:col-span-2">
            <input
              required
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Category">
            <select
              value={category}
              onChange={(event) =>
                setCategory(event.target.value as CaseCategory)
              }
              className="input"
            >
              <option value="Customer">Customer</option>
              <option value="Contract">Contract</option>
              <option value="Supplier">Supplier</option>
              <option value="Employee">Employee</option>
              <option value="Project">Project</option>
              <option value="Other">Other</option>
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
              <option value="New">New</option>
              <option value="Under Review">Under Review</option>
              <option value="In Progress">In Progress</option>
              <option value="Waiting">Waiting</option>
              <option value="Completed">Completed</option>
              <option value="Critical">Critical</option>
            </select>
          </Field>

          <Field label="Risk">
            <select
              value={risk}
              onChange={(event) =>
                setRisk(event.target.value as RiskLevel)
              }
              className="input"
            >
              <option value="Low">Low</option>
              <option value="Medium">Medium</option>
              <option value="High">High</option>
            </select>
          </Field>

          <Field label="Responsible person">
            <input
              value={responsiblePerson}
              onChange={(event) => setResponsiblePerson(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Company / Department">
            <input
              value={companyDepartment}
              onChange={(event) => setCompanyDepartment(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="External contact">
            <input
              value={externalContact}
              onChange={(event) => setExternalContact(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Primary deadline">
            <input
              type="date"
              value={primaryDeadline}
              onChange={(event) => setPrimaryDeadline(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Follow-up date">
            <input
              type="date"
              value={followUpDate}
              onChange={(event) => setFollowUpDate(event.target.value)}
              className="input"
            />
          </Field>

          <Field label="Next action" className="sm:col-span-2">
            <textarea
              value={nextAction}
              onChange={(event) => setNextAction(event.target.value)}
              rows={3}
              className="input"
            />
          </Field>

          <Field label="Description" className="sm:col-span-2">
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
              Cancel
            </button>

            <button
              type="submit"
              disabled={saving || !title.trim()}
              className="rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
