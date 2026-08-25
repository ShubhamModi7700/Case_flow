import TaskForm from "../TaskForm";
import TaskList from "../TaskList";
import type { TaskItem } from "../../types";

export default function TasksTab({ caseId, tasks, onTaskCreated, onTaskUpdated, refreshHistory, canEdit }: {
  caseId: number;
  tasks: TaskItem[];
  onTaskCreated: (task: TaskItem) => void;
  onTaskUpdated: (task: TaskItem) => void;
  refreshHistory: () => Promise<void>;
  canEdit: boolean;
}) {
  return (
    <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
      {canEdit ? (
        <TaskForm caseId={caseId} onTaskCreated={(task) => { onTaskCreated(task); void refreshHistory(); }} />
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">Nur-Lese-Zugriff: Aufgaben können nicht geändert werden.</div>
      )}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-950">Aufgabenübersicht</h2>
        <p className="mt-1 text-sm text-slate-500">{tasks.length} {tasks.length === 1 ? "Aufgabe" : "Aufgaben"}</p>
        <div className="mt-5">
          <TaskList tasks={tasks} onTaskUpdated={(task) => { onTaskUpdated(task); void refreshHistory(); }} />
        </div>
      </section>
    </div>
  );
}
