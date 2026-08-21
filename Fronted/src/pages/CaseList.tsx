import axios from "axios";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Link,
  useSearchParams,
} from "react-router-dom";

import { api } from "../api";
import {
  translateRisk,
  translateStatus,
} from "../i18n/de";
import { getRiskConfig } from "../utils/riskStyles";
import {
  type CaseItem,
  formatCaseNumber,
} from "../types";

type SortOption =
  | "priority"
  | "caseAsc"
  | "caseDesc"
  | "newest"
  | "oldest";

export default function CaseList() {
  const [searchParams, setSearchParams] =
    useSearchParams();

  const [cases, setCases] = useState<CaseItem[]>([]);

  const [search, setSearch] = useState(
    searchParams.get("search") ?? "",
  );

  const [status, setStatus] = useState(
    searchParams.get("status") ?? "",
  );

  const [risk, setRisk] = useState(
    searchParams.get("risk") ?? "",
  );

  const [sortBy, setSortBy] = useState<SortOption>(
    (searchParams.get("sort") as SortOption) ??
      "priority",
  );

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadCases = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const response = await api.get<CaseItem[]>(
        "/cases/",
        {
          params: {
            search:
              searchParams.get("search") ||
              undefined,

            status:
              searchParams.get("status") ||
              undefined,

            status_group:
              searchParams.get("status_group") ||
              undefined,

            risk:
              searchParams.get("risk") ||
              undefined,

            overdue:
              searchParams.get("overdue") ===
                "true" || undefined,

            upcoming:
              searchParams.get("upcoming") ===
                "true" || undefined,

            missing_owner:
              searchParams.get("missing_owner") ===
                "true" || undefined,

            missing_next_action:
              searchParams.get(
                "missing_next_action",
              ) === "true" || undefined,
          },
        },
      );

      setCases(response.data);
    } catch (requestError: unknown) {
      console.error(
        "Fälle konnten nicht geladen werden:",
        requestError,
      );

      if (axios.isAxiosError(requestError)) {
        const statusCode =
          requestError.response?.status;

        const detail =
          requestError.response?.data?.detail;

        if (typeof detail === "string") {
          setError(detail);
        } else if (statusCode === 401) {
          setError(
            "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.",
          );
        } else if (statusCode) {
          setError(
            `Fälle konnten nicht geladen werden. Serverstatus: ${statusCode}.`,
          );
        } else {
          setError(
            "Das Backend konnte nicht erreicht werden.",
          );
        }
      } else {
        setError(
          "Fälle konnten nicht geladen werden.",
        );
      }
    } finally {
      setLoading(false);
    }
  }, [searchParams]);

  useEffect(() => {
    void loadCases();
  }, [loadCases]);

  const sortedCases = useMemo(() => {
    const result = [...cases];

    switch (sortBy) {
      case "caseAsc":
        return result.sort(
          (firstCase, secondCase) =>
            firstCase.id - secondCase.id,
        );

      case "caseDesc":
        return result.sort(
          (firstCase, secondCase) =>
            secondCase.id - firstCase.id,
        );

      case "newest":
        return result.sort(
          (firstCase, secondCase) =>
            getDateValue(secondCase.created_at) -
            getDateValue(firstCase.created_at),
        );

      case "oldest":
        return result.sort(
          (firstCase, secondCase) =>
            getDateValue(firstCase.created_at) -
            getDateValue(secondCase.created_at),
        );

      case "priority":
      default:
        // Die vom Backend gelieferte Prioritätsreihenfolge
        // wird unverändert übernommen.
        return result;
    }
  }, [cases, sortBy]);

  function handleSearch(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const next = new URLSearchParams(
      searchParams,
    );

    search
      ? next.set("search", search)
      : next.delete("search");

    status
      ? next.set("status", status)
      : next.delete("status");

    risk
      ? next.set("risk", risk)
      : next.delete("risk");

    sortBy !== "priority"
      ? next.set("sort", sortBy)
      : next.delete("sort");

    next.delete("status_group");

    setSearchParams(next);
  }

  function handleSortChange(
    event: React.ChangeEvent<HTMLSelectElement>,
  ) {
    const nextSort = event.target
      .value as SortOption;

    setSortBy(nextSort);

    const next = new URLSearchParams(
      searchParams,
    );

    if (nextSort === "priority") {
      next.delete("sort");
    } else {
      next.set("sort", nextSort);
    }

    setSearchParams(next);
  }

  function setCaseGroup(group: "" | "open" | "completed") {
    const next = new URLSearchParams(searchParams);

    if (group) {
      next.set("status_group", group);
      next.delete("status");
    } else {
      next.delete("status_group");
    }

    // Group navigation is about the lifecycle state; remove dashboard-only
    // filters that could make the result unexpectedly empty.
    next.delete("overdue");
    next.delete("upcoming");
    next.delete("missing_owner");
    next.delete("missing_next_action");

    setStatus("");
    setSearchParams(next);
  }

  function clearFilters() {
    setSearch("");
    setStatus("");
    setRisk("");
    setSortBy("priority");
    setSearchParams({});
  }

  const activeFilter =
    getActiveFilterLabel(searchParams);

  return (
    <div className="mx-auto max-w-7xl p-8">
      <header className="mb-6 flex items-start justify-between gap-6">
        <div>
          <h1 className="text-3xl font-bold text-slate-950">
            Fälle
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            Alle Geschäftsfälle suchen,
            priorisieren und bearbeiten.
          </p>
        </div>

        <Link
          to="/cases/new"
          className="shrink-0 rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white"
        >
          + Fall anlegen
        </Link>
      </header>

      <div className="mb-5 inline-flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
        <button
          type="button"
          onClick={() => setCaseGroup("")}
          className={`rounded-lg px-4 py-2 text-sm font-semibold ${
            !searchParams.get("status_group")
              ? "bg-slate-950 text-white"
              : "text-slate-600 hover:bg-slate-50"
          }`}
        >
          Alle
        </button>
        <button
          type="button"
          onClick={() => setCaseGroup("open")}
          className={`rounded-lg px-4 py-2 text-sm font-semibold ${
            searchParams.get("status_group") === "open"
              ? "bg-slate-950 text-white"
              : "text-slate-600 hover:bg-slate-50"
          }`}
        >
          Offen
        </button>
        <button
          type="button"
          onClick={() => setCaseGroup("completed")}
          className={`rounded-lg px-4 py-2 text-sm font-semibold ${
            searchParams.get("status_group") === "completed"
              ? "bg-emerald-600 text-white"
              : "text-slate-600 hover:bg-slate-50"
          }`}
        >
          Abgeschlossen
        </button>
      </div>

      {activeFilter && (
        <div className="mb-4 flex items-center justify-between gap-4 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          <span>
            Aktiver Management-Filter:{" "}
            <strong>{activeFilter}</strong>
          </span>

          <button
            type="button"
            onClick={clearFilters}
            className="shrink-0 font-semibold hover:underline"
          >
            Filter entfernen
          </button>
        </div>
      )}

      <form
        onSubmit={handleSearch}
        className="mb-6 grid gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-2 xl:grid-cols-[minmax(280px,1fr)_170px_150px_210px_auto_auto]"
      >
        <input
          value={search}
          onChange={(event) =>
            setSearch(event.target.value)
          }
          placeholder="Fallnummer, Titel, Unternehmen, Kontakt oder Verantwortliche Person"
          className="rounded-xl border border-slate-300 px-4 py-3"
        />

        <select
          value={status}
          onChange={(event) =>
            setStatus(event.target.value)
          }
          className="rounded-xl border border-slate-300 px-4 py-3"
        >
          <option value="">Alle Status</option>
          <option value="New">Neu</option>
          <option value="Under Review">
            In Prüfung
          </option>
          <option value="In Progress">
            In Bearbeitung
          </option>
          <option value="Waiting">
            Wartend
          </option>
          <option value="Completed">
            Abgeschlossen
          </option>
          <option value="Critical">
            Kritisch
          </option>
        </select>

        <select
          value={risk}
          onChange={(event) =>
            setRisk(event.target.value)
          }
          className="rounded-xl border border-slate-300 px-4 py-3"
        >
          <option value="">Alle Risiken</option>
          <option value="Low">Niedrig</option>
          <option value="Medium">Mittel</option>
          <option value="High">Hoch</option>
        </select>

        <select
          value={sortBy}
          onChange={handleSortChange}
          className="rounded-xl border border-slate-300 px-4 py-3"
          aria-label="Sortierung"
        >
          <option value="priority">
            Priorität
          </option>

          <option value="caseAsc">
            Fallnummer aufsteigend
          </option>

          <option value="caseDesc">
            Fallnummer absteigend
          </option>

          <option value="newest">
            Neueste zuerst
          </option>

          <option value="oldest">
            Älteste zuerst
          </option>
        </select>

        <button
          type="submit"
          disabled={loading}
          className="rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Lädt..." : "Suchen"}
        </button>

        <button
          type="button"
          onClick={clearFilters}
          className="rounded-xl border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700"
        >
          Zurücksetzen
        </button>
      </form>

      {error && (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <p className="p-6 text-slate-500">
            Fälle werden geladen...
          </p>
        ) : sortedCases.length === 0 ? (
          <div className="p-10 text-center">
            <p className="font-medium text-slate-700">
              Keine Fälle gefunden
            </p>
          </div>
        ) : (
          <table className="w-full min-w-[1000px]">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="p-4">
                  Fallnummer
                </th>
                <th className="p-4">Titel</th>
                <th className="p-4">
                  Unternehmen / Abteilung
                </th>
                <th className="p-4">
                  Verantwortlich
                </th>
                <th className="p-4">Status</th>
                <th className="p-4">Risiko</th>
                <th className="p-4">Frist</th>
                <th className="p-4">
                  Nächste Maßnahme
                </th>
              </tr>
            </thead>

            <tbody>
              {sortedCases.map((caseItem) => (
                <tr
                  key={caseItem.id}
                  className="border-t border-slate-100 text-sm hover:bg-slate-50"
                >
                  <td className="p-4">
                    <Link
                      to={`/cases/${caseItem.id}`}
                      className="font-semibold text-slate-950 hover:underline"
                    >
                      {formatCaseNumber(
                        caseItem.id,
                      )}
                    </Link>
                  </td>

                  <td className="p-4">
                    <Link
                      to={`/cases/${caseItem.id}`}
                      className="font-semibold text-slate-950 hover:underline"
                    >
                      {caseItem.title}
                    </Link>
                  </td>

                  <td className="p-4 text-slate-600">
                    {caseItem.company}

                    {caseItem.department
                      ? ` — ${caseItem.department}`
                      : ""}
                  </td>

                  <td className="p-4 text-slate-600">
                    {caseItem.responsible_person ??
                      "Nicht zugewiesen"}
                  </td>

                  <td className="p-4">
                    <Badge
                      value={caseItem.status}
                      label={translateStatus(
                        caseItem.status,
                      )}
                    />
                  </td>

                  <td className="p-4">
                    <Badge
                      value={caseItem.risk}
                      label={translateRisk(
                        caseItem.risk,
                      )}
                    />
                  </td>

                  <td
                    className={`p-4 ${
                      isOverdue(
                        caseItem.primary_deadline,
                        caseItem.status,
                      )
                        ? "font-semibold text-red-700"
                        : "text-slate-600"
                    }`}
                  >
                    {caseItem.status === "Completed"
                      ? "Keine"
                      : caseItem.primary_deadline ?? "–"}
                  </td>

                  <td
                    className={`max-w-xs truncate p-4 ${
                      caseItem.next_action
                        ? "text-slate-600"
                        : "font-semibold text-amber-700"
                    }`}
                  >
                    {caseItem.status === "Completed"
                      ? "Keine – Fall abgeschlossen"
                      : caseItem.next_action ?? "Fehlt"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function getActiveFilterLabel(
  params: URLSearchParams,
): string {
  if (params.get("overdue") === "true") {
    return "Überfällige Fristen";
  }

  if (params.get("upcoming") === "true") {
    return "Anstehende Fristen";
  }

  if (
    params.get("missing_owner") === "true"
  ) {
    return "Ohne verantwortliche Person";
  }

  if (
    params.get("missing_next_action") ===
    "true"
  ) {
    return "Ohne nächste Maßnahme";
  }

  if (
    params.get("status_group") === "open"
  ) {
    return "Offene Fälle";
  }

  if (
    params.get("status_group") === "completed"
  ) {
    return "Abgeschlossene Fälle";
  }

  if (params.get("risk") === "High") {
    return "Hohes Risiko";
  }

  if (params.get("risk") === "Medium") {
    return "Mittleres Risiko";
  }

  if (params.get("risk") === "Low") {
    return "Niedriges Risiko";
  }

  return "";
}

function isOverdue(
  deadline: string | null,
  status: string,
): boolean {
  if (!deadline || status === "Completed") {
    return false;
  }

  return (
    deadline <
    new Date().toISOString().slice(0, 10)
  );
}

function getDateValue(
  value: string | null | undefined,
): number {
  if (!value) {
    return 0;
  }

  const timestamp = new Date(value).getTime();

  return Number.isNaN(timestamp)
    ? 0
    : timestamp;
}

function Badge({
  value,
  label,
}: {
  value: string;
  label: string;
}) {
  const statusStyles: Record<string, string> = {
    New: "bg-slate-100 text-slate-700",
    "Under Review":
      "bg-blue-100 text-blue-700",
    "In Progress":
      "bg-indigo-100 text-indigo-700",
    Waiting:
      "bg-amber-100 text-amber-700",
    Completed:
      "bg-green-100 text-green-700",
    Critical:
      "bg-red-100 text-red-700",
  };

  const className = [
    "Low",
    "Medium",
    "High",
  ].includes(value)
    ? getRiskConfig(value).badgeClass
    : statusStyles[value] ??
      "bg-slate-100 text-slate-700";

  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${className}`}
    >
      {label}
    </span>
  );
}