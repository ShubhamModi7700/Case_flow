export default function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`border-b-2 px-4 py-3 text-sm font-medium ${active ? "border-slate-950 text-slate-950" : "border-transparent text-slate-500 hover:text-slate-950"}`}
    >
      {label}
    </button>
  );
}
