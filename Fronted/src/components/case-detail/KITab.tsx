export default function KITab() {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-10 shadow-sm">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-lg font-bold text-slate-600">
        KI
      </div>

      <h2 className="mt-5 text-center text-xl font-semibold text-slate-950">
        KI-Assistent
      </h2>

      <p className="mx-auto mt-3 max-w-2xl text-center text-sm leading-6 text-slate-500">
        Dieser Bereich unterstützt das Management bei der schnellen Bewertung
        eines Falls. Künftig werden hier automatisch Zusammenfassungen,
        Risikohinweise, empfohlene nächste Maßnahmen und relevante Dokumente
        angezeigt.
      </p>
    </section>
  );
}
