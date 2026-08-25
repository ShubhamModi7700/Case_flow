import { useMemo, useState } from "react";

import { api } from "../api";
import type { TaskItem } from "../types";

interface TaskListProps {
  tasks: TaskItem[];
  onTaskUpdated: (task: TaskItem) => void;
  onTaskDeleted: (taskId: number) => void;
}

type StatusFilter = "All" | "Open" | "Completed" | "Overdue";

export default function TaskList({
  tasks,
  onTaskUpdated,
  onTaskDeleted,
}: TaskListProps) {
  const [workingTaskId, setWorkingTaskId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("All");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [personFilter, setPersonFilter] = useState("");

  const categories = useMemo(() => [...new Set(tasks.map(t => t.category).filter(Boolean) as string[])].sort(), [tasks]);
  const people = useMemo(() => [...new Set(tasks.flatMap(t => splitPeople(t.responsible_person)))].sort(), [tasks]);
  const completedCount = tasks.filter(t => t.status === "Completed").length;
  const openCount = tasks.length - completedCount;
  const overdueCount = tasks.filter(isTaskOverdue).length;
  const progress = tasks.length ? Math.round((completedCount / tasks.length) * 100) : 0;

  const visibleTasks = tasks.filter(task => {
    if (statusFilter === "Open" && task.status !== "Open") return false;
    if (statusFilter === "Completed" && task.status !== "Completed") return false;
    if (statusFilter === "Overdue" && !isTaskOverdue(task)) return false;
    if (categoryFilter && task.category !== categoryFilter) return false;
    if (personFilter && !splitPeople(task.responsible_person).includes(personFilter)) return false;
    return true;
  });

  async function completeTask(taskId: number): Promise<void> {
    try {
      setWorkingTaskId(taskId); setError("");
      const response = await api.patch<TaskItem>(`/tasks/${taskId}/complete`);
      onTaskUpdated(response.data);
    } catch (requestError: unknown) {
      console.error(requestError);
      setError(getApiErrorMessage(requestError, "Die Aufgabe konnte nicht abgeschlossen werden."));
    } finally { setWorkingTaskId(null); }
  }

  async function deleteTask(task: TaskItem): Promise<void> {
    const confirmed = window.confirm(
      `Möchten Sie die Aufgabe „${task.title}“ wirklich löschen?`,
    );

    if (!confirmed) {
      return;
    }

    try {
      setWorkingTaskId(task.id);
      setError("");

      await api.delete(`/tasks/${task.id}`);
      onTaskDeleted(task.id);
    } catch (requestError: unknown) {
      console.error(requestError);
      setError(
        getApiErrorMessage(
          requestError,
          "Die Aufgabe konnte nicht gelöscht werden.",
        ),
      );
    } finally {
      setWorkingTaskId(null);
    }
  }

  if (tasks.length === 0) return <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Noch keine Aufgaben vorhanden.</p>;

  return <div className="space-y-5">
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Stat label="Gesamt" value={tasks.length} />
      <Stat label="Offen" value={openCount} />
      <Stat label="Erledigt" value={completedCount} />
      <Stat label="Überfällig" value={overdueCount} danger={overdueCount > 0} />
    </div>

    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center justify-between text-sm"><span className="font-medium text-slate-700">Fortschritt</span><span className="font-semibold text-slate-950">{progress}%</span></div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${progress}%` }} /></div>
    </div>

    <div className="grid gap-3 md:grid-cols-3">
      <select className="input" value={statusFilter} onChange={e => setStatusFilter(e.target.value as StatusFilter)}>
        <option value="All">Alle Status</option><option value="Open">Offen</option><option value="Completed">Erledigt</option><option value="Overdue">Überfällig</option>
      </select>
      <select className="input" value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}>
        <option value="">Alle Bereiche</option>{categories.map(c => <option key={c} value={c}>{c}</option>)}
      </select>
      <select className="input" value={personFilter} onChange={e => setPersonFilter(e.target.value)}>
        <option value="">Alle Verantwortlichen</option>{people.map(person => <option key={person} value={person}>{person}</option>)}
      </select>
    </div>

    {error && <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
    <p className="text-xs text-slate-500">{visibleTasks.length} von {tasks.length} Aufgaben angezeigt</p>

    <div className="space-y-3">{visibleTasks.map(task => {
      const overdue=isTaskOverdue(task), completed=task.status === "Completed", working=workingTaskId === task.id;
      return <article key={task.id} className={`rounded-xl border p-4 ${overdue ? "border-red-200 bg-red-50" : "border-slate-200 bg-white"}`}>
        <div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><h3 className={`font-semibold text-slate-950 ${completed ? "line-through opacity-60" : ""}`}>{task.title}</h3><PriorityBadge priority={task.priority} />{task.category && <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-700">{task.category}</span>}{overdue && <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700">Überfällig</span>}</div>
          {task.description && <p className="mt-2 text-sm text-slate-600">{task.description}</p>}
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500"><span><b>Verantwortlich:</b> {task.responsible_person ?? "Nicht zugewiesen"}</span><span><b>Fällig:</b> {task.due_date ?? "Keine Frist"}</span></div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {completed ? (
            <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">
              Erledigt
            </span>
          ) : (
            <button
              type="button"
              disabled={working}
              onClick={() => void completeTask(task.id)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50"
            >
              {working ? "Wird verarbeitet..." : "Als erledigt markieren"}
            </button>
          )}

          <button
            type="button"
            disabled={working}
            onClick={() => void deleteTask(task)}
            className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
          >
            Löschen
          </button>
        </div>
        </div>
      </article>;
    })}</div>
  </div>;
}

function Stat({label,value,danger=false}:{label:string;value:number;danger?:boolean}) { return <div className={`rounded-xl border p-4 ${danger ? "border-red-200 bg-red-50" : "border-slate-200 bg-white"}`}><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p><p className={`mt-2 text-2xl font-bold ${danger ? "text-red-700" : "text-slate-950"}`}>{value}</p></div>; }
function splitPeople(value:string|null):string[]{ return value ? value.split(/[,;]+/).map(v=>v.trim()).filter(Boolean) : []; }
function PriorityBadge({ priority }: { priority: string }) { const styles:Record<string,string>={Low:"bg-green-100 text-green-700",Medium:"bg-amber-100 text-amber-700",High:"bg-red-100 text-red-700"}; return <span className={`rounded-full px-3 py-1 text-xs font-semibold ${styles[priority] ?? "bg-slate-100 text-slate-700"}`}>{priority === "Low" ? "Niedrig" : priority === "Medium" ? "Mittel" : "Hoch"}</span>; }
function isTaskOverdue(task:TaskItem):boolean { if(task.status === "Completed" || !task.due_date) return false; const today=new Date(); today.setHours(0,0,0,0); return new Date(`${task.due_date}T00:00:00`) < today; }
function getApiErrorMessage(error:unknown,fallback:string):string { if(typeof error === "object" && error !== null && "response" in error){ const response=(error as {response?:{data?:{detail?:string|Array<{msg?:string}>}}}).response; const detail=response?.data?.detail; if(typeof detail === "string") return detail; if(Array.isArray(detail)){const m=detail.map(i=>i.msg).filter(Boolean).join("; "); if(m)return m;}} return fallback; }
