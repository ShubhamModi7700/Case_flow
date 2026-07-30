export default function KITab() {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-10 shadow-sm">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-lg font-bold text-slate-600">
        KI
      </div>

      <h2 className="mt-5 text-center text-xl font-semibold text-slate-950">
        KI-Managementassistent
      </h2>

      <p className="mx-auto mt-3 max-w-2xl text-center text-sm leading-6 text-slate-500">
        Dieser Bereich unterstützt das Management bei der schnellen Bewertung
        eines Falls. Künftig werden hier automatisch Zusammenfassungen,
        Risikohinweise, empfohlene nächste Maßnahmen und relevante Dokumente
        angezeigt.
      </p>

      <div className="mt-8 rounded-xl bg-slate-50 p-6">
        <h3 className="font-semibold text-slate-900">
          Geplante KI-Funktionen
        </h3>

        <ul className="mt-4 list-disc space-y-2 pl-5 text-sm text-slate-600">
          <li>Management-Zusammenfassung des Falls</li>
          <li>Empfohlene nächste Maßnahmen</li>
          <li>Hinweise auf offene Fristen</li>
          <li>Risikobewertung mit Begründung</li>
          <li>Übersicht relevanter Dokumente</li>
        </ul>
      </div>
    </section>
  );
}