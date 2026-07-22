import { useState } from "react";

import { api } from "../api";
import type { TaskItem } from "../types";

type TaskPriority = "Low" | "Medium" | "High";

interface TaskFormProps {
  caseId: number;
  onTaskCreated: (task: TaskItem) => void;
}

export default function TaskForm({
  caseId,
  onTaskCreated,
}: TaskFormProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [responsiblePerson, setResponsiblePerson] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("Medium");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function createTask(
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    const normalizedTitle = title.trim();

    if (!normalizedTitle) {
      setError("Task title is required.");
      return;
    }

    try {
      setSubmitting(true);
      setError("");

      const response = await api.post<TaskItem>(
        `/cases/${caseId}/tasks`,
        {
          title: normalizedTitle,
          description: description.trim() || null,
          responsible_person: responsiblePerson.trim() || null,
          due_date: dueDate || null,
          priority,
          status: "Open",
        },
      );

      onTaskCreated(response.data);

      setTitle("");
      setDescription("");
      setResponsiblePerson("");
      setDueDate("");
      setPriority("Medium");
    } catch (requestError: unknown) {
      console.error(requestError);
      setError(
        getApiErrorMessage(
          requestError,
          "The task could not be created.",
        ),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">Add task</h2>

      {error && (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <form onSubmit={createTask} className="mt-5 space-y-4">
        <Field label="Title">
          <input
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="input"
          />
        </Field>

        <Field label="Description">
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={3}
            className="input"
          />
        </Field>

        <Field label="Responsible person">
          <input
            value={responsiblePerson}
            onChange={(event) => setResponsiblePerson(event.target.value)}
            className="input"
          />
        </Field>

        <Field label="Due date">
          <input
            type="date"
            value={dueDate}
            onChange={(event) => setDueDate(event.target.value)}
            className="input"
          />
        </Field>

        <Field label="Priority">
          <select
            value={priority}
            onChange={(event) =>
              setPriority(event.target.value as TaskPriority)
            }
            className="input"
          >
            <option value="Low">Low</option>
            <option value="Medium">Medium</option>
            <option value="High">High</option>
          </select>
        </Field>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Adding task..." : "Add task"}
        </button>
      </form>
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </span>
      {children}
    </label>
  );
}

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error
  ) {
    const response = (
      error as {
        response?: {
          data?: {
            detail?: string | Array<{ msg?: string }>;
          };
        };
      }
    ).response;

    const detail = response?.data?.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      const message = detail
        .map((item) => item.msg)
        .filter(Boolean)
        .join("; ");

      if (message) {
        return message;
      }
    }
  }

  return fallback;
}