import { useState } from "react";

import { api } from "../api";
import type { TaskItem } from "../types";

interface TaskListProps {
  tasks: TaskItem[];
  onTaskUpdated: (task: TaskItem) => void;
}

export default function TaskList({
  tasks,
  onTaskUpdated,
}: TaskListProps) {
  const [workingTaskId, setWorkingTaskId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function completeTask(taskId: number): Promise<void> {
    try {
      setWorkingTaskId(taskId);
      setError("");

      const response = await api.patch<TaskItem>(
        `/tasks/${taskId}/complete`,
      );

      onTaskUpdated(response.data);
    } catch (requestError: unknown) {
      console.error(requestError);
      setError(
        getApiErrorMessage(
          requestError,
          "Die Aufgabe konnte nicht abgeschlossen werden.",
        ),
      );
    } finally {
      setWorkingTaskId(null);
    }
  }

  if (tasks.length === 0) {
    return (
      <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">
        No tasks have been added.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {tasks.map((task) => {
        const overdue = isTaskOverdue(task);
        const completed = task.status === "Completed";
        const working = workingTaskId === task.id;

        return (
          <article
            key={task.id}
            className={`rounded-xl border p-4 ${
              overdue
                ? "border-red-200 bg-red-50"
                : "border-slate-200 bg-white"
            }`}
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3
                    className={`font-semibold text-slate-950 ${
                      completed ? "line-through opacity-60" : ""
                    }`}
                  >
                    {task.title}
                  </h3>

                  <PriorityBadge priority={task.priority} />

                  {overdue && (
                    <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700">
                      Überfällig
                    </span>
                  )}
                </div>

                {task.description && (
                  <p className="mt-2 text-sm text-slate-600">
                    {task.description}
                  </p>
                )}

                <p className="mt-3 text-xs text-slate-500">
                  Responsible: {task.responsible_person ?? "Nicht zugewiesen"}
                </p>

                <p className="mt-1 text-xs text-slate-500">
                  Due: {task.due_date ?? "Keine Frist"}
                </p>
              </div>

              {completed ? (
                <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">
                  Abgeschlossen
                </span>
              ) : (
                <button
                  type="button"
                  disabled={working}
                  onClick={() => void completeTask(task.id)}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {working ? "Completing..." : "Complete"}
                </button>
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const styles: Record<string, string> = {
    Low: "bg-green-100 text-green-700",
    Medium: "bg-amber-100 text-amber-700",
    High: "bg-red-100 text-red-700",
  };

  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-semibold ${
        styles[priority] ?? "bg-slate-100 text-slate-700"
      }`}
    >
      {priority}
    </span>
  );
}

function isTaskOverdue(task: TaskItem): boolean {
  if (task.status === "Completed" || !task.due_date) {
    return false;
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const dueDate = new Date(`${task.due_date}T00:00:00`);
  return dueDate < today;
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