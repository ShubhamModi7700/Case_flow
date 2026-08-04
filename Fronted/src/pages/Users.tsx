import { useEffect, useState } from "react";

import { api } from "../api";
import { useAuth } from "../AuthContext";
import type {
  UserCreatePayload,
  UserItem,
  UserRole,
} from "../types";

const emptyForm: UserCreatePayload = {
  full_name: "",
  email: "",
  password: "",
  role: "User",
  is_active: true,
};

export default function Users() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [form, setForm] = useState<UserCreatePayload>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function loadUsers(): Promise<void> {
    try {
      setLoading(true);
      setError("");
      const response = await api.get<UserItem[]>("/users/");
      setUsers(response.data);
    } catch {
      setError("Benutzer konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadUsers();
  }, []);

  async function handleCreate(
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    try {
      setSubmitting(true);
      setError("");
      await api.post("/users/", form);
      setForm(emptyForm);
      await loadUsers();
    } catch {
      setError("Der Benutzer konnte nicht erstellt werden. Prüfen Sie E-Mail-Adresse und Passwort.");
    } finally {
      setSubmitting(false);
    }
  }

  async function updateUser(
    target: UserItem,
    changes: Partial<{
      role: UserRole;
      is_active: boolean;
      password: string;
    }>,
  ): Promise<void> {
    try {
      setError("");
      await api.patch(`/users/${target.id}`, changes);
      await loadUsers();
    } catch {
      setError("Der Benutzer konnte nicht aktualisiert werden.");
    }
  }

  async function resetPassword(target: UserItem): Promise<void> {
    const password = window.prompt(
      `Neues Passwort eingeben für ${target.full_name} (minimum 8 characters):`,
    );

    if (!password) return;

    if (password.length < 8) {
      setError("Das neue Passwort muss mindestens 8 Zeichen enthalten.");
      return;
    }

    await updateUser(target, { password });
  }

  if (currentUser?.role !== "Manager") {
    return (
      <div className="p-8">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700">
          Managerzugriff ist erforderlich.
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mx-auto max-w-6xl space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-950">Benutzer</h1>
          <p className="mt-2 text-sm text-slate-500">
            Create individual logins and manage access. Nur Manager können diese Seite verwenden.
          </p>
        </div>

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        <form
          onSubmit={handleCreate}
          className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm md:grid-cols-2"
        >
          <h2 className="text-lg font-semibold md:col-span-2">Benutzer hinzufügen</h2>

          <label>
            <span className="mb-2 block text-sm font-medium">Vollständiger Name</span>
            <input
              className="input"
              required
              value={form.full_name}
              onChange={(event) =>
                setForm({ ...form, full_name: event.target.value })
              }
            />
          </label>

          <label>
            <span className="mb-2 block text-sm font-medium">E-Mail</span>
            <input
              className="input"
              type="email"
              required
              value={form.email}
              onChange={(event) =>
                setForm({ ...form, email: event.target.value })
              }
            />
          </label>

          <label>
            <span className="mb-2 block text-sm font-medium">Passwort</span>
            <input
              className="input"
              type="password"
              minLength={8}
              required
              value={form.password}
              onChange={(event) =>
                setForm({ ...form, password: event.target.value })
              }
            />
          </label>

          <label>
            <span className="mb-2 block text-sm font-medium">Rolle</span>
            <select
              className="input"
              value={form.role}
              onChange={(event) =>
                setForm({
                  ...form,
                  role: event.target.value as UserRole,
                })
              }
            >
              <option value="User">Benutzer</option>
              <option value="Manager">Manager</option>
              <option value="Viewer">Betrachter</option>
            </select>
          </label>

          <div className="md:col-span-2">
            <button
              className="rounded-xl bg-slate-950 px-5 py-3 font-semibold text-white disabled:opacity-50"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "Wird erstellt..." : "Benutzer erstellen"}
            </button>
          </div>
        </form>

        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          {loading ? (
            <p className="p-6 text-sm text-slate-500">Benutzer werden geladen...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-5 py-4">Name</th>
                    <th className="px-5 py-4">E-Mail</th>
                    <th className="px-5 py-4">Rolle</th>
                    <th className="px-5 py-4">Status</th>
                    <th className="px-5 py-4">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((item) => (
                    <tr key={item.id} className="border-b border-slate-100 last:border-0">
                      <td className="px-5 py-4 font-medium text-slate-900">
                        {item.full_name}
                      </td>
                      <td className="px-5 py-4 text-slate-600">{item.email}</td>
                      <td className="px-5 py-4">
                        <select
                          className="rounded-lg border border-slate-300 px-2 py-1"
                          value={item.role}
                          disabled={item.id === currentUser.id}
                          onChange={(event) =>
                            void updateUser(item, {
                              role: event.target.value as UserRole,
                            })
                          }
                        >
                          <option value="User">Benutzer</option>
                          <option value="Manager">Manager</option>
              <option value="Viewer">Betrachter</option>
                        </select>
                      </td>
                      <td className="px-5 py-4">
                        {item.is_active ? "Aktiv" : "Deaktiviert"}
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => void resetPassword(item)}
                            className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium"
                          >
                            Reset password
                          </button>
                          <button
                            type="button"
                            disabled={item.id === currentUser.id}
                            onClick={() =>
                              void updateUser(item, {
                                is_active: !item.is_active,
                              })
                            }
                            className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium disabled:opacity-40"
                          >
                            {item.is_active ? "Deaktivieren" : "Aktivieren"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
