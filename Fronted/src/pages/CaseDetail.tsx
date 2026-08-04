import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../AuthContext";
import { RiskBadge, StatusBadge } from "../components/case-detail/Badges";
import DeleteCaseModal from "../components/case-detail/DeleteCaseModal";
import DocumentsTab from "../components/case-detail/DocumentsTab";
import EditCaseModal from "../components/case-detail/EditCaseModal";
import KITab from "../components/case-detail/KITab";
import OverviewTab from "../components/case-detail/OverviewTab";
import TabButton from "../components/case-detail/TabButton";
import TasksTab from "../components/case-detail/TasksTab";
import TimelineTab from "../components/case-detail/TimelineTab";
import type {
  CaseUpdatePayload,
  TabName,
} from "../components/case-detail/types";
import {
  type CaseItem,
  type DocumentItem,
  type TaskItem,
  type TimelineEvent,
  formatCaseNumber,
} from "../types";

export default function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const canEdit = user?.role === "Manager" || user?.role === "User";
  const isManager = user?.role === "Manager";

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

  const [deletingCase, setDeletingCase] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  async function loadCaseDetail(): Promise<void> {
    if (!caseId || !/^\d+$/.test(caseId)) {
      setError(
        "Ungültige Fall-ID. Öffnen Sie den Fall über die Fallübersicht.",
      );
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError("");

      const [
        caseResponse,
        taskResponse,
        documentResponse,
        timelineResponse,
      ] = await Promise.all([
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
      console.error(
        "Falldetails konnten nicht geladen werden:",
        requestError,
      );

      setError(
        "Die Falldetails konnten nicht geladen werden. Prüfen Sie die Backend-Routen und die ausgewählte Fall-ID.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadTimeline(): Promise<void> {
    if (!caseId || !/^\d+$/.test(caseId)) {
      return;
    }

    try {
      const response = await api.get<TimelineEvent[]>(
        `/cases/${caseId}/timeline`,
      );

      setTimeline(response.data);
    } catch (requestError) {
      console.error(
        "Der Verlauf konnte nicht aktualisiert werden:",
        requestError,
      );
    }
  }

  function handleTaskCreated(task: TaskItem): void {
    setTasks((currentTasks) => [task, ...currentTasks]);
  }

  function handleTaskUpdated(task: TaskItem): void {
    setTasks((currentTasks) =>
      currentTasks.map((currentTask) =>
        currentTask.id === task.id ? task : currentTask,
      ),
    );
  }

  async function deleteCase(): Promise<void> {
    if (!caseItem || deletingCase) {
      return;
    }

    try {
      setDeletingCase(true);
      setDeleteError("");

      await api.delete(`/cases/${caseItem.id}`);

      setShowDeleteModal(false);
      navigate("/cases", { replace: true });
    } catch (requestError: any) {
      console.error(
        "Fall konnte nicht gelöscht werden:",
        requestError,
      );

      const detail = requestError.response?.data?.detail;

      setDeleteError(
        typeof detail === "string"
          ? detail
          : "Der Fall konnte nicht gelöscht werden. Bitte versuchen Sie es erneut.",
      );
    } finally {
      setDeletingCase(false);
    }
  }

  async function saveCase(
    updatedValues: CaseUpdatePayload,
  ): Promise<void> {
    if (!caseItem) {
      return;
    }

    try {
      setSavingCase(true);
      setEditError("");

      const response = await api.patch<CaseItem>(
        `/cases/${caseItem.id}`,
        updatedValues,
      );

      setCaseItem(response.data);
      setEditingCase(false);

      await loadTimeline();
    } catch (requestError: any) {
      console.error(
        "Fallaktualisierung fehlgeschlagen:",
        requestError,
      );

      const detail = requestError.response?.data?.detail;

      if (typeof detail === "string") {
        setEditError(detail);
      } else if (Array.isArray(detail)) {
        const validationMessage = detail
          .map((item) => item?.msg)
          .filter(Boolean)
          .join("; ");

        setEditError(
          validationMessage ||
            "Der Fall konnte nicht aktualisiert werden.",
        );
      } else {
        setEditError(
          "Der Fall konnte nicht aktualisiert werden.",
        );
      }
    } finally {
      setSavingCase(false);
    }
  }

  useEffect(() => {
    void loadCaseDetail();
  }, [caseId]);

  if (loading) {
    return (
      <div className="p-8 text-slate-500">
        Falldetails werden geladen...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
          {error}
        </div>

        <Link
          to="/cases"
          className="mt-4 inline-block text-sm font-medium text-slate-600 hover:text-slate-950"
        >
          ← Zurück zu den Fällen
        </Link>
      </div>
    );
  }

  if (!caseItem) {
    return (
      <div className="p-8">
        <p>Fall wurde nicht gefunden.</p>

        <Link
          to="/cases"
          className="mt-4 inline-block text-sm font-medium text-slate-600 hover:text-slate-950"
        >
          ← Zurück zu den Fällen
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl p-8">
      <Link
        to="/cases"
        className="text-sm font-medium text-slate-500 hover:text-slate-950"
      >
        ← Zurück zu den Fällen
      </Link>

      <header className="mt-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
            {formatCaseNumber(caseItem.id)}
          </p>

          <h1 className="mt-2 text-3xl font-bold text-slate-950">
            {caseItem.title}
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            {caseItem.company}
            {caseItem.department
              ? ` — ${caseItem.department}`
              : ""}
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            <StatusBadge value={caseItem.status} />
            <RiskBadge value={caseItem.risk} />
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          {canEdit && (
          <button
            type="button"
            onClick={() => {
              setEditError("");
              setEditingCase(true);
            }}
            className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Fall bearbeiten
          </button>
          )}

          {isManager && (
          <button
            type="button"
            onClick={() => {
              setDeleteError("");
              setShowDeleteModal(true);
            }}
            className="rounded-xl border border-red-300 bg-red-50 px-5 py-3 text-sm font-semibold text-red-700 hover:bg-red-100"
          >
            Fall löschen
          </button>
          )}
        </div>
      </header>

      <div className="mt-8 border-b border-slate-200">
        <nav className="flex flex-wrap gap-2">
          <TabButton
            label="Übersicht"
            active={activeTab === "overview"}
            onClick={() => setActiveTab("overview")}
          />

          <TabButton
            label={`Aufgaben (${tasks.length})`}
            active={activeTab === "tasks"}
            onClick={() => setActiveTab("tasks")}
          />

          <TabButton
            label={`Dokumente (${documents.length})`}
            active={activeTab === "documents"}
            onClick={() => setActiveTab("documents")}
          />

          <TabButton
            label={`Verlauf (${timeline.length})`}
            active={activeTab === "timeline"}
            onClick={() => setActiveTab("timeline")}
          />

          <TabButton
            label="KI-Assistent"
            active={activeTab === "KI"}
            onClick={() => setActiveTab("KI")}
          />
        </nav>
      </div>

      <div className="mt-6">
        {activeTab === "overview" && (
          <OverviewTab
            caseItem={caseItem}
            tasks={tasks}
            documents={documents}
            timeline={timeline}
            canEdit={canEdit}
            isManager={isManager}
            onEditCase={() => {
              setEditError("");
              setEditingCase(true);
            }}
            onRiskConfirmed={(updatedCase) => {
              setCaseItem(updatedCase);
              void loadTimeline();
            }}
          />
        )}

        {activeTab === "tasks" && (
          <TasksTab
            caseId={caseItem.id}
            tasks={tasks}
            onTaskCreated={handleTaskCreated}
            onTaskUpdated={handleTaskUpdated}
            refreshHistory={loadTimeline}
            canEdit={canEdit}
          />
        )}

        {activeTab === "documents" && (
          <DocumentsTab
            documents={documents}
            reload={loadCaseDetail}
            isManager={isManager}
          />
        )}

        {activeTab === "timeline" && (
          <TimelineTab
            caseId={caseItem.id}
            events={timeline}
            canEdit={canEdit}
            onEventAdded={(event) =>
              setTimeline((currentEvents) => [
                event,
                ...currentEvents,
              ])
            }
          />
        )}

        {activeTab === "KI" && <KITab />}
      </div>

      {editingCase && (
        <EditCaseModal
          caseItem={caseItem}
          saving={savingCase}
          error={editError}
          onCancel={() => {
            if (!savingCase) {
              setEditingCase(false);
            }
          }}
          onSave={saveCase}
        />
      )}

      {showDeleteModal && (
        <DeleteCaseModal
          caseTitle={caseItem.title}
          deleting={deletingCase}
          error={deleteError}
          onCancel={() => {
            if (!deletingCase) {
              setDeleteError("");
              setShowDeleteModal(false);
            }
          }}
          onConfirm={deleteCase}
        />
      )}
    </div>
  );
}