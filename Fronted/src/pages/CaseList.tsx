import axios from "axios";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import {
  type CaseItem,
  formatCaseNumber,
} from "../types";

export default function CaseList() {
  const [cases, setCases] = useState<CaseItem[]>(
    [],
  );
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [risk, setRisk] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadCases() {
    try {
      setLoading(true);
      setError("");

      const response = await api.get<CaseItem[]>(
        "/cases/",
        {
          params: {
            search: search || undefined,
            status: status || undefined,
            risk: risk || undefined,
          },
        },
      );

      setCases(response.data);
    } catch (requestError: unknown) {
      console.error(
        "Loading cases failed:",
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
            "Your session has expired. Please sign in again.",
          );
        } else if (statusCode) {
          setError(
            `Cases could not be loaded. Server returned ${statusCode}.`,
          );
        } else {
          setError(
            "The backend could not be reached.",
          );
        }
      } else {
        setError("Cases could not be loaded.");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadCases();
  }, []);

  function handleSearch(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    void loadCases();
  }

  return (
    <div className="mx-auto max-w-7xl p-8">
      <header className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-950">
            Cases
          </h1>

          <p className="mt-2 text-sm text-slate-500">
            Search and manage all business cases.
          </p>
        </div>

        <Link
          to="/cases/new"
          className="rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white"
        >
          + Create case
        </Link>
      </header>

      <form
        onSubmit={handleSearch}
        className="mb-6 grid gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-[1fr_180px_160px_auto]"
      >
        <input
          value={search}
          onChange={(event) =>
            setSearch(event.target.value)
          }
          placeholder="Search title, company, contact or responsible person"
          className="rounded-xl border border-slate-300 px-4 py-3"
        />

        <select
          value={status}
          onChange={(event) =>
            setStatus(event.target.value)
          }
          className="rounded-xl border border-slate-300 px-4 py-3"
        >
          <option value="">All statuses</option>
          <option value="New">New</option>
          <option value="Under Review">
            Under Review
          </option>
          <option value="In Progress">
            In Progress
          </option>
          <option value="Waiting">Waiting</option>
          <option value="Completed">
            Completed
          </option>
          <option value="Critical">
            Critical
          </option>
        </select>

        <select
          value={risk}
          onChange={(event) =>
            setRisk(event.target.value)
          }
          className="rounded-xl border border-slate-300 px-4 py-3"
        >
          <option value="">All risks</option>
          <option value="Low">Low</option>
          <option value="Medium">Medium</option>
          <option value="High">High</option>
        </select>

        <button
          type="submit"
          disabled={loading}
          className="rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Loading..." : "Search"}
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
            Loading cases...
          </p>
        ) : cases.length === 0 ? (
          <div className="p-10 text-center">
            <p className="font-medium text-slate-700">
              No cases found
            </p>
          </div>
        ) : (
          <table className="w-full min-w-[1000px]">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="p-4">Case ID</th>
                <th className="p-4">Title</th>
                <th className="p-4">
                  Company / Department
                </th>
                <th className="p-4">
                  Responsible
                </th>
                <th className="p-4">Status</th>
                <th className="p-4">Risk</th>
                <th className="p-4">
                  Deadline
                </th>
                <th className="p-4">
                  Next action
                </th>
              </tr>
            </thead>

            <tbody>
              {cases.map((caseItem) => (
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

                  <td className="p-4">
                    <Link
                      to={`/cases/${caseItem.id}`}
                      className="font-semibold text-slate-950 hover:underline"
                    >
                      {caseItem.company}
                      {caseItem.department
                        ? ` — ${caseItem.department}`
                        : ""}
                    </Link>
                  </td>

                  <td className="p-4 text-slate-600">
                    {caseItem.responsible_person ??
                      "Not assigned"}
                  </td>

                  <td className="p-4">
                    <Badge
                      value={caseItem.status}
                    />
                  </td>

                  <td className="p-4">
                    <Badge
                      value={caseItem.risk}
                    />
                  </td>

                  <td className="p-4 text-slate-600">
                    {caseItem.primary_deadline ??
                      "-"}
                  </td>

                  <td className="max-w-xs truncate p-4 text-slate-600">
                    {caseItem.next_action ??
                      "Missing"}
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

function Badge({
  value,
}: {
  value: string;
}) {
  const styles: Record<string, string> = {
    Low: "bg-green-100 text-green-700",
    Medium: "bg-amber-100 text-amber-700",
    High: "bg-red-100 text-red-700",

    New: "bg-slate-100 text-slate-700",
    "Under Review":
      "bg-blue-100 text-blue-700",
    "In Progress":
      "bg-indigo-100 text-indigo-700",
    Waiting: "bg-amber-100 text-amber-700",
    Completed:
      "bg-green-100 text-green-700",
    Critical: "bg-red-100 text-red-700",
  };

  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
        styles[value] ??
        "bg-slate-100 text-slate-700"
      }`}
    >
      {value}
    </span>
  );
}