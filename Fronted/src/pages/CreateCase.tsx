import axios from "axios";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../AuthContext";
import CaseAccessSelector from "../components/CaseAccessSelector";
import { getRiskConfig } from "../utils/riskStyles";
import type { CaseAccessInput, CaseItem, UserItem } from "../types";

type CaseForm = {
  title: string;
  company: string;
  department: string;
  category: string;
  external_contact: string;
  responsible_person: string;
  status: string;
  risk: string;
  financial_amount: string;
  description: string;
  next_action: string;
  primary_deadline: string;
  follow_up_date: string;
};

const initialForm: CaseForm = {
  title: "",
  company: "",
  department: "",
  category: "Customer",
  external_contact: "",
  responsible_person: "",
  status: "New",
  risk: "Low",
  financial_amount: "",
  description: "",
  next_action: "",
  primary_deadline: "",
  follow_up_date: "",
};

export default function CreateCase() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const canManageAccess =
    user?.role === "Manager";

  const [form, setForm] = useState<CaseForm>(initialForm);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [access, setAccess] = useState<CaseAccessInput[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!canManageAccess) return;

    api
      .get<UserItem[]>("/users/")
      .then((response) => setUsers(response.data))
      .catch(() => setUsers([]));
  }, [canManageAccess]);

  function handleChange(
    event: React.ChangeEvent<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >,
  ) {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!form.title.trim()) {
      setError("Ein Titel ist erforderlich.");
      return;
    }

    try {
      setSubmitting(true);
      setError("");

      const payload = {
        title: form.title.trim(),
        company: form.company.trim() || null,
        department: form.department.trim() || null,
        category: form.category,
        external_contact:
          form.external_contact.trim() || null,
        responsible_person:
          form.responsible_person.trim() || null,
        status: form.status,
        risk: form.risk,
        financial_amount: form.financial_amount
          ? Number(form.financial_amount)
          : null,
        description: form.description.trim() || null,
        next_action: form.next_action.trim() || null,
        primary_deadline:
          form.primary_deadline || null,
        follow_up_date:
          form.follow_up_date || null,
        access: canManageAccess ? access : [],
      };

      const response = await api.post<CaseItem>(
        "/cases/",
        payload,
      );

      navigate(`/cases/${response.data.id}`, {
        replace: true,
      });
    } catch (requestError: unknown) {
      console.error("Fallerstellung fehlgeschlagen:", requestError);

      if (axios.isAxiosError(requestError)) {
        const status = requestError.response?.status;
        const detail = requestError.response?.data?.detail;

        if (typeof detail === "string") {
          setError(detail);
        } else if (Array.isArray(detail)) {
          setError(
            detail
              .map((item) => item?.msg)
              .filter(Boolean)
              .join("; ") ||
              "Die übermittelten Daten sind ungültig.",
          );
        } else if (status === 401) {
          setError(
            "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
          );
        } else if (status === 405) {
          setError(
            "Die API-Route ist nicht korrekt konfiguriert. Prüfen Sie die Vercel-Weiterleitung.",
          );
        } else if (status) {
          setError(
            `Der Fall konnte nicht angelegt werden. Der Server meldete Status ${status}.`,
          );
        } else {
          setError(
            "Das Backend konnte nicht erreicht werden.",
          );
        }
      } else {
        setError(
          "Beim Anlegen des Falls ist ein unerwarteter Fehler aufgetreten.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-slate-950">
          Fall anlegen
        </h1>

        <p className="mt-2 text-sm text-slate-500">
          Nur der Titel ist erforderlich. Alle weiteren Angaben können
          ergänzt werden, sobald sie verfügbar sind.
        </p>
      </header>

      {error && (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
          {error}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="grid gap-5 rounded-2xl border border-slate-200 bg-white p-7 shadow-sm md:grid-cols-2"
      >
        <Field label="Titel" wide>
          <input
            name="title"
            value={form.title}
            onChange={handleChange}
            required
            minLength={3}
            className="input"
          />
        </Field>

        <Field label="Unternehmen">
          <input
            name="company"
            value={form.company}
            onChange={handleChange}
            className="input"
          />
        </Field>

        <Field label="Abteilung">
          <input
            name="department"
            value={form.department}
            onChange={handleChange}
            className="input"
          />
        </Field>

        <Field label="Kategorie">
          <select
            name="category"
            value={form.category}
            onChange={handleChange}
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

        <Field label="Externer Kontakt">
          <input
            name="external_contact"
            value={form.external_contact}
            onChange={handleChange}
            className="input"
          />
        </Field>

        <Field label="Verantwortliche Person">
          <input
            name="responsible_person"
            value={form.responsible_person}
            onChange={handleChange}
            className="input"
          />
        </Field>

        <Field label="Status">
          <select
            name="status"
            value={form.status}
            onChange={handleChange}
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
            name="risk"
            value={form.risk}
            onChange={handleChange}
            className={`input font-semibold transition-colors ${getRiskConfig(form.risk).selectClass}`}
          >
            <option value="Low">Niedrig</option>
            <option value="Medium">Mittel</option>
            <option value="High">Hoch</option>
          </select>
        </Field>

        <Field label="Finanzieller Betrag (EUR)">
          <input
            type="number"
            min="0"
            step="0.01"
            name="financial_amount"
            value={form.financial_amount}
            onChange={handleChange}
            placeholder="z. B. 50000"
            className="input"
          />
        </Field>

        <Field label="Hauptfrist">
          <input
            type="date"
            name="primary_deadline"
            value={form.primary_deadline}
            onChange={handleChange}
            className="input"
          />
        </Field>

        <Field label="Wiedervorlage">
          <input
            type="date"
            name="follow_up_date"
            value={form.follow_up_date}
            onChange={handleChange}
            className="input"
          />
        </Field>

        <Field label="Beschreibung" wide>
          <textarea
            name="description"
            value={form.description}
            onChange={handleChange}
            rows={4}
            className="input"
          />
        </Field>

        <Field label="Nächste Maßnahme" wide>
          <textarea
            name="next_action"
            value={form.next_action}
            onChange={handleChange}
            rows={4}
            className="input"
          />
        </Field>

        {canManageAccess && (
          <div className="md:col-span-2">
            <CaseAccessSelector
              users={users}
              value={access}
              onChange={setAccess}
            />
          </div>
        )}

        <div className="flex justify-end md:col-span-2">
          <button
            type="submit"
            disabled={submitting || !form.title.trim()}
            className="rounded-xl bg-slate-950 px-6 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting
              ? "Wird angelegt..."
              : "Fall anlegen"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({
  label,
  children,
  wide = false,
}: {
  label: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <label
      className={wide ? "md:col-span-2" : ""}
    >
      <span className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </span>

      {children}
    </label>
  );
}