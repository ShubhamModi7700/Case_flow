import type { CaseAccessInput, UserItem } from "../types";

type Props = {
  users: UserItem[];
  value: CaseAccessInput[];
  onChange: (value: CaseAccessInput[]) => void;
  disabled?: boolean;
};

export default function CaseAccessSelector({
  users,
  value,
  onChange,
  disabled = false,
}: Props) {
  const selectable = users.filter(
    (user) =>
      user.is_active &&
      !["Manager", "Shareholder"].includes(user.role),
  );

  function toggle(userId: number, checked: boolean) {
    if (!checked) {
      onChange(value.filter((item) => item.user_id !== userId));
      return;
    }
    onChange([...value, { user_id: userId, can_edit: false }]);
  }

  function setEdit(userId: number, canEdit: boolean) {
    onChange(
      value.map((item) =>
        item.user_id === userId ? { ...item, can_edit: canEdit } : item,
      ),
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="mb-3">
        <p className="text-sm font-semibold text-slate-900">
          Zugriffsberechtigung
        </p>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          Geschäftsführung und Shareholder sehen automatisch alle Fälle.
          Wählen Sie hier Mitarbeiter aus, die diesen Fall sehen dürfen.
        </p>
      </div>

      {selectable.length === 0 ? (
        <p className="text-sm text-slate-500">
          Keine aktiven Mitarbeiter verfügbar.
        </p>
      ) : (
        <div className="space-y-2">
          {selectable.map((user) => {
            const selected = value.find((item) => item.user_id === user.id);
            return (
              <div
                key={user.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2"
              >
                <label className="flex min-w-0 items-center gap-3">
                  <input
                    type="checkbox"
                    disabled={disabled}
                    checked={Boolean(selected)}
                    onChange={(event) => toggle(user.id, event.target.checked)}
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-slate-900">
                      {user.full_name}
                    </span>
                    <span className="block truncate text-xs text-slate-500">
                      {user.email}
                    </span>
                  </span>
                </label>

                {selected && (
                  <select
                    disabled={disabled}
                    value={selected.can_edit ? "edit" : "view"}
                    onChange={(event) =>
                      setEdit(user.id, event.target.value === "edit")
                    }
                    className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="view">Nur ansehen</option>
                    <option value="edit">Bearbeiten</option>
                  </select>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
