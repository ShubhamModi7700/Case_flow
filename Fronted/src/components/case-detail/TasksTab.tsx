import TaskForm from "../TaskForm";
import TaskList from "../TaskList";
import type { TaskItem } from "../../types";

export default function TasksTab({ caseId, tasks, onTaskCreated, onTaskUpdated, refreshHistory }: {
  caseId: number;
  tasks: TaskItem[];
  onTaskCreated: (task: TaskItem) => void;
  onTaskUpdated: (task: TaskItem) => void;
  refreshHistory: () => Promise<void>;
}) {
  return (
    <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
      <TaskForm caseId={caseId} onTaskCreated={(task) => { onTaskCreated(task); void refreshHistory(); }} />
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-950">Aufgaben</h2>
        <p className="mt-1 text-sm text-slate-500">{tasks.length} {tasks.length === 1 ? "task" : "tasks"}</p>
        <div className="mt-5">
          <TaskList tasks={tasks} onTaskUpdated={(task) => { onTaskUpdated(task); void refreshHistory(); }} />
        </div>
      </section>
    </div>
  );
}
