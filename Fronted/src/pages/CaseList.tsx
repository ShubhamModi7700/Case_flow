import axios from "axios";
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api";
import { translateRisk, translateStatus } from "../i18n/de";
import { type CaseItem, formatCaseNumber } from "../types";

export default function CaseList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [status, setStatus] = useState(searchParams.get("status") ?? "");
  const [risk, setRisk] = useState(searchParams.get("risk") ?? "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadCases = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const response = await api.get<CaseItem[]>("/cases/", {
        params: {
          search: searchParams.get("search") || undefined,
          status: searchParams.get("status") || undefined,
          status_group: searchParams.get("status_group") || undefined,
          risk: searchParams.get("risk") || undefined,
          overdue: searchParams.get("overdue") === "true" || undefined,
          upcoming: searchParams.get("upcoming") === "true" || undefined,
          missing_owner: searchParams.get("missing_owner") === "true" || undefined,
          missing_next_action: searchParams.get("missing_next_action") === "true" || undefined,
        },
      });
      setCases(response.data);
    } catch (requestError: unknown) {
      console.error("Loading cases failed:", requestError);
      if (axios.isAxiosError(requestError)) {
        const statusCode = requestError.response?.status;
        const detail = requestError.response?.data?.detail;
        if (typeof detail === "string") setError(detail);
        else if (statusCode === 401) setError("Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.");
        else if (statusCode) setError(`Fälle konnten nicht geladen werden. Serverstatus: ${statusCode}.`);
        else setError("Das Backend konnte nicht erreicht werden.");
      } else setError("Fälle konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, [searchParams]);

  useEffect(() => { void loadCases(); }, [loadCases]);

  function handleSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = new URLSearchParams(searchParams);
    search ? next.set("search", search) : next.delete("search");
    status ? next.set("status", status) : next.delete("status");
    risk ? next.set("risk", risk) : next.delete("risk");
    next.delete("status_group");
    setSearchParams(next);
  }

  function clearFilters() {
    setSearch(""); setStatus(""); setRisk(""); setSearchParams({});
  }

  const activeFilter = getActiveFilterLabel(searchParams);

  return (
    <div className="mx-auto max-w-7xl p-8">
      <header className="mb-6 flex items-start justify-between">
        <div><h1 className="text-3xl font-bold text-slate-950">Fälle</h1><p className="mt-2 text-sm text-slate-500">Alle Geschäftsfälle suchen, priorisieren und bearbeiten.</p></div>
        <Link to="/cases/new" className="rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white">+ Fall anlegen</Link>
      </header>

      {activeFilter && <div className="mb-4 flex items-center justify-between rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800"><span>Aktiver Management-Filter: <strong>{activeFilter}</strong></span><button type="button" onClick={clearFilters} className="font-semibold hover:underline">Filter entfernen</button></div>}

      <form onSubmit={handleSearch} className="mb-6 grid gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-[1fr_180px_160px_auto_auto]">
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Fallnummer, Titel, Unternehmen, Kontakt oder Verantwortliche Person" className="rounded-xl border border-slate-300 px-4 py-3" />
        <select value={status} onChange={(event) => setStatus(event.target.value)} className="rounded-xl border border-slate-300 px-4 py-3">
          <option value="">Alle Status</option><option value="New">Neu</option><option value="Under Review">In Prüfung</option><option value="In Progress">In Bearbeitung</option><option value="Waiting">Wartend</option><option value="Completed">Abgeschlossen</option><option value="Critical">Kritisch</option>
        </select>
        <select value={risk} onChange={(event) => setRisk(event.target.value)} className="rounded-xl border border-slate-300 px-4 py-3">
          <option value="">Alle Risiken</option><option value="Low">Niedrig</option><option value="Medium">Mittel</option><option value="High">Hoch</option>
        </select>
        <button type="submit" disabled={loading} className="rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">{loading ? "Lädt..." : "Suchen"}</button>
        <button type="button" onClick={clearFilters} className="rounded-xl border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700">Zurücksetzen</button>
      </form>

      {error && <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>}
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading ? <p className="p-6 text-slate-500">Fälle werden geladen...</p> : cases.length === 0 ? <div className="p-10 text-center"><p className="font-medium text-slate-700">Keine Fälle gefunden</p></div> : (
          <table className="w-full min-w-[1000px]">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"><tr><th className="p-4">Fallnummer</th><th className="p-4">Titel</th><th className="p-4">Unternehmen / Abteilung</th><th className="p-4">Verantwortlich</th><th className="p-4">Status</th><th className="p-4">Risiko</th><th className="p-4">Frist</th><th className="p-4">Nächste Maßnahme</th></tr></thead>
            <tbody>{cases.map((caseItem) => <tr key={caseItem.id} className="border-t border-slate-100 text-sm hover:bg-slate-50">
              <td className="p-4"><Link to={`/cases/${caseItem.id}`} className="font-semibold text-slate-950 hover:underline">{formatCaseNumber(caseItem.id)}</Link></td>
              <td className="p-4"><Link to={`/cases/${caseItem.id}`} className="font-semibold text-slate-950 hover:underline">{caseItem.title}</Link></td>
              <td className="p-4 text-slate-600">{caseItem.company}{caseItem.department ? ` — ${caseItem.department}` : ""}</td>
              <td className="p-4 text-slate-600">{caseItem.responsible_person ?? "Nicht zugewiesen"}</td>
              <td className="p-4"><Badge value={caseItem.status} label={translateStatus(caseItem.status)} /></td>
              <td className="p-4"><Badge value={caseItem.risk} label={translateRisk(caseItem.risk)} /></td>
              <td className={`p-4 ${isOverdue(caseItem.primary_deadline, caseItem.status) ? "font-semibold text-red-700" : "text-slate-600"}`}>{caseItem.primary_deadline ?? "–"}</td>
              <td className={`max-w-xs truncate p-4 ${caseItem.next_action ? "text-slate-600" : "font-semibold text-amber-700"}`}>{caseItem.next_action ?? "Fehlt"}</td>
            </tr>)}</tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function getActiveFilterLabel(params: URLSearchParams): string {
  if (params.get("overdue") === "true") return "Überfällige Fristen";
  if (params.get("upcoming") === "true") return "Anstehende Fristen";
  if (params.get("missing_owner") === "true") return "Ohne verantwortliche Person";
  if (params.get("missing_next_action") === "true") return "Ohne nächste Maßnahme";
  if (params.get("status_group") === "open") return "Offene Fälle";
  if (params.get("risk") === "High") return "Hohes Risiko";
  return "";
}

function isOverdue(deadline: string | null, status: string): boolean {
  if (!deadline || status === "Completed") return false;
  return deadline < new Date().toISOString().slice(0, 10);
}

function Badge({ value, label }: { value: string; label: string }) {
  const styles: Record<string, string> = { Low: "bg-green-100 text-green-700", Medium: "bg-amber-100 text-amber-700", High: "bg-red-100 text-red-700", New: "bg-slate-100 text-slate-700", "Under Review": "bg-blue-100 text-blue-700", "In Progress": "bg-indigo-100 text-indigo-700", Waiting: "bg-amber-100 text-amber-700", Completed: "bg-green-100 text-green-700", Critical: "bg-red-100 text-red-700" };
  return <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${styles[value] ?? "bg-slate-100 text-slate-700"}`}>{label}</span>;
}
