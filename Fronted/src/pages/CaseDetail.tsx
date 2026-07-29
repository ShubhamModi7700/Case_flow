import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import AITab from "../components/case-detail/AITab";
import { RiskBadge, StatusBadge } from "../components/case-detail/Badges";
import DocumentsTab from "../components/case-detail/DocumentsTab";
import EditCaseModal from "../components/case-detail/EditCaseModal";
import TimelineTab from "../components/case-detail/TimelineTab";
import OverviewTab from "../components/case-detail/OverviewTab";
import TabButton from "../components/case-detail/TabButton";
import TasksTab from "../components/case-detail/TasksTab";
import type { CaseUpdatePayload, TabName } from "../components/case-detail/types";
import {
  type CaseItem,
  type DocumentItem,
  type TimelineEvent,
  type TaskItem,
  formatCaseNumber,
} from "../types";

export default function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>();
  const [activeTab, setActiveTab] = useState<TabName>("overview");
  const [caseItem, setCaseItem] = useState<CaseItem | null>(null);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editingCase, setEditingCase] = useState(false);
  const [savingCase, setSavingCase] = useState(false);
  const [editError, setEditError] = useState("");

  async function loadCaseDetail(): Promise<void> {
    if (!caseId || !/^\d+$/.test(caseId)) {
      setError("Invalid case ID. Open the case from the Cases page.");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError("");
      const [caseResponse, taskResponse, documentResponse, timelineResponse] = await Promise.all([
        api.get<CaseItem>(`/cases/${caseId}`),
        api.get<TaskItem[]>(`/cases/${caseId}/tasks`),
        api.get<DocumentItem[]>(`/cases/${caseId}/documents`),
        api.get<TimelineEvent[]>(`/cases/${caseId}/timeline`),
      ]);

      setCaseItem(caseResponse.data);
      setTasks(taskResponse.data);
      setDocuments(documentResponse.data);
      setTimeline(timelineResponse.data);
    } catch (requestError) {
      console.error(requestError);
      setError("The case details could not be loaded. Check the backend routes and the selected case ID.");
    } finally {
      setLoading(false);
    }
  }

  async function loadTimeline(): Promise<void> {
    if (!caseId || !/^\d+$/.test(caseId)) return;
    try {
      const response = await api.get<TimelineEvent[]>(`/cases/${caseId}/timeline`);
      setTimeline(response.data);
    } catch (requestError) {
      console.error("Timeline refresh failed:", requestError);
    }
  }

  function handleTaskCreated(task: TaskItem): void {
    setTasks((currentTasks) => [task, ...currentTasks]);
  }

  function handleTaskUpdated(task: TaskItem): void {
    setTasks((currentTasks) => currentTasks.map((currentTask) => currentTask.id === task.id ? task : currentTask));
  }

  async function saveCase(updatedValues: CaseUpdatePayload): Promise<void> {
    if (!caseItem) return;
    try {
      setSavingCase(true);
      setEditError("");
      const response = await api.patch<CaseItem>(`/cases/${caseItem.id}`, updatedValues);
      setCaseItem(response.data);
      setEditingCase(false);
      await loadTimeline();
    } catch (requestError: any) {
      console.error("Case update failed:", requestError);
      const detail = requestError.response?.data?.detail;
      if (typeof detail === "string") setEditError(detail);
      else if (Array.isArray(detail)) setEditError(detail.map((item) => item?.msg).filter(Boolean).join("; ") || "The case could not be updated.");
      else setEditError("The case could not be updated.");
    } finally {
      setSavingCase(false);
    }
  }

  useEffect(() => {
    void loadCaseDetail();
  }, [caseId]);

  if (loading) return <div className="p-8 text-slate-500">Loading case details...</div>;

  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>
        <Link to="/cases" className="mt-4 inline-block text-sm font-medium text-slate-600 hover:text-slate-950">← Back to cases</Link>
      </div>
    );
  }

  if (!caseItem) {
    return (
      <div className="p-8">
        <p>Case not found.</p>
        <Link to="/cases" className="mt-4 inline-block text-sm font-medium text-slate-600 hover:text-slate-950">← Back to cases</Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl p-8">
      <Link to="/cases" className="text-sm font-medium text-slate-500 hover:text-slate-950">← Back to cases</Link>

      <header className="mt-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">{formatCaseNumber(caseItem.id)}</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-950">{caseItem.title}</h1>
          <p className="mt-2 text-sm text-slate-500">{caseItem.company}{caseItem.department ? ` — ${caseItem.department}` : ""}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusBadge value={caseItem.status} />
            <RiskBadge value={caseItem.risk} />
          </div>
        </div>

        <button type="button" onClick={() => { setEditError(""); setEditingCase(true); }} className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50">Edit case</button>
      </header>

      <div className="mt-8 border-b border-slate-200">
        <nav className="flex flex-wrap gap-2">
          <TabButton label="Overview" active={activeTab === "overview"} onClick={() => setActiveTab("overview")} />
          <TabButton label={`Tasks (${tasks.length})`} active={activeTab === "tasks"} onClick={() => setActiveTab("tasks")} />
          <TabButton label={`Documents (${documents.length})`} active={activeTab === "documents"} onClick={() => setActiveTab("documents")} />
          <TabButton label={`Timeline (${timeline.length})`} active={activeTab === "timeline"} onClick={() => setActiveTab("timeline")} />
          <TabButton label="AI" active={activeTab === "ai"} onClick={() => setActiveTab("ai")} />
        </nav>
      </div>

      <div className="mt-6">
        {activeTab === "overview" && <OverviewTab caseItem={caseItem} />}
        {activeTab === "tasks" && <TasksTab caseId={caseItem.id} tasks={tasks} onTaskCreated={handleTaskCreated} onTaskUpdated={handleTaskUpdated} refreshHistory={loadTimeline} />}
        {activeTab === "documents" && <DocumentsTab documents={documents} reload={loadCaseDetail} />}
        {activeTab === "timeline" && <TimelineTab caseId={caseItem.id} events={timeline} onEventAdded={(event) => setTimeline((current) => [event, ...current])} />}
        {activeTab === "ai" && <AITab />}
      </div>

      {editingCase && (
        <EditCaseModal
          caseItem={caseItem}
          saving={savingCase}
          error={editError}
          onCancel={() => { if (!savingCase) setEditingCase(false); }}
          onSave={saveCase}
        />
      )}
    </div>
  );
}
