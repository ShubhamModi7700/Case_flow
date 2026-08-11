import { useState, type FormEvent } from "react";

import { api } from "../../api";
import type { TimelineEvent, TimelineEventCreatePayload } from "../../types";
import {
  commonLabels,
  translateEventTitle,
  translateTimelineType,
} from "../../i18n/de";
import { formatDateTime } from "./formatters";

const EVENT_STYLES: Record<string, string> = {
  Created: "bg-emerald-500",
  Completed: "bg-emerald-500",
  Document: "bg-sky-500",
  Note: "bg-violet-500",
  Milestone: "bg-amber-500",
  "Task deadline": "bg-orange-500",
  Task: "bg-indigo-500",
  Archived: "bg-slate-500",
  Update: "bg-blue-500",
  AI: "bg-fuchsia-500",
};

const EVENT_ICONS: Record<string, string> = {
  Created: "✓",
  Completed: "✓",
  Document: "▣",
  Note: "✎",
  Milestone: "◆",
  "Task deadline": "◷",
  Task: "☑",
  Archived: "□",
  Update: "↻",
  AI: "✦",
};

interface TimelineTabProps {
  caseId: number;
  events: TimelineEvent[];
  onEventAdded: (event: TimelineEvent) => void;
  canEdit: boolean;
}

export default function TimelineTab({
  caseId,
  events,
  onEventAdded,
  canEdit,
}: TimelineTabProps) {
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [eventType, setEventType] =
    useState<TimelineEventCreatePayload["event_type"]>("Note");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    if (!title.trim()) {
      return;
    }

    try {
      setSaving(true);
      setError("");

      const payload: TimelineEventCreatePayload = {
        title: title.trim(),
        description: description.trim() || null,
        event_type: eventType,
      };

      const response = await api.post<TimelineEvent>(
        `/cases/${caseId}/timeline`,
        payload,
      );

      onEventAdded(response.data);
      setTitle("");
      setDescription("");
      setEventType("Note");
      setShowForm(false);
    } catch (requestError) {
      console.error(requestError);
      setError(
        "Der Zeitleisteneintrag konnte nicht gespeichert werden.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            {commonLabels.timelineTitle}
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            {commonLabels.timelineDescription}
          </p>
        </div>

        {canEdit && (
        <button
          type="button"
          onClick={() => setShowForm((value) => !value)}
          className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
        >
          {showForm
            ? commonLabels.cancel
            : `+ ${commonLabels.addEntry}`}
        </button>
        )}
      </div>

      {showForm && (
        <form
          onSubmit={submit}
          className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4"
        >
          <div className="grid gap-4 md:grid-cols-[180px_1fr]">
            <select
              value={eventType}
              onChange={(event) =>
                setEventType(
                  event.target
                    .value as TimelineEventCreatePayload["event_type"],
                )
              }
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              <option value="Note">Notiz</option>
              <option value="Update">Aktualisierung</option>
              <option value="Milestone">Meilenstein</option>
            </select>

            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={commonLabels.timelineEntryTitlePlaceholder}
              required
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            />
          </div>

          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder={commonLabels.optionalDetails}
            rows={3}
            className="mt-3 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          />

          {error && (
            <p className="mt-2 text-sm text-red-600">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={saving}
            className="mt-3 rounded-lg bg-slate-950 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {saving
              ? commonLabels.saving
              : commonLabels.saveEntry}
          </button>
        </form>
      )}

      {events.length === 0 ? (
        <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">
          {commonLabels.noTimelineEvents}
        </p>
      ) : (
        <div className="mt-7">
          {events.map((entry, index) => (
            <article
              key={entry.id}
              className="relative grid grid-cols-[24px_1fr] gap-4 pb-7 last:pb-0"
            >
              {index < events.length - 1 && (
                <div className="absolute left-[13px] top-6 h-full w-px bg-slate-200" />
              )}

              <div
                className={`relative z-10 mt-0.5 flex h-7 w-7 items-center justify-center rounded-full border-4 border-white text-[10px] font-bold text-white shadow-sm ${
                  EVENT_STYLES[entry.event_type] ?? "bg-slate-500"
                }`}
                aria-hidden="true"
              >
                {EVENT_ICONS[entry.event_type] ?? "•"}
              </div>

              <div
                className={`rounded-xl border p-4 ${
                  entry.is_future
                    ? "border-amber-200 bg-amber-50"
                    : "border-slate-200 bg-white"
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                      {translateTimelineType(entry.event_type)}
                    </span>

                    <h3 className="mt-1 font-semibold text-slate-950">
                      {translateEventTitle(entry.title)}
                    </h3>
                  </div>

                  {entry.is_future && (
                    <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800">
                      {commonLabels.upcoming}
                    </span>
                  )}
                </div>

                {entry.description && (
                  <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600">
                    {translateEventTitle(entry.description)}
                  </p>
                )}

                <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-400">
                  <span>{formatDateTime(entry.occurred_at)}</span>
                  <span aria-hidden="true">·</span>
                  <span>Von {entry.person ?? commonLabels.system}</span>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}