export type View = "map" | "assets";

interface Props {
  view: View;
  setView: (v: View) => void;
  assistantOpen: boolean;
  toggleAssistant: () => void;
}

const ICONS: Record<View, JSX.Element> = {
  map: (
    <path d="M9 3 3 5v16l6-2 6 2 6-2V3l-6 2-6-2Zm0 0v16m6-14v16" />
  ),
  assets: (
    <path d="M3 5h18M3 12h18M3 19h18" />
  ),
};

export default function NavRail({ view, setView, assistantOpen, toggleAssistant }: Props) {
  const Item = ({ id, label }: { id: View; label: string }) => (
    <button
      onClick={() => setView(id)}
      title={label}
      className={`group flex h-11 w-11 items-center justify-center rounded-xl transition ${
        view === id ? "bg-accent/15 text-accent-300" : "text-slate-500 hover:bg-white/5 hover:text-slate-200"
      }`}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-5 w-5">
        {ICONS[id]}
      </svg>
    </button>
  );

  return (
    <div className="flex w-14 flex-col items-center gap-2 border-r border-line bg-ink-900 py-3">
      <div
        className="mb-2 grid h-8 w-8 grid-cols-2 grid-rows-2 gap-[2px] rounded-[4px] border border-accent/40 bg-ink-850 p-1"
        title="gridwatch"
      >
        <span className="rounded-[1px] bg-accent" />
        <span className="rounded-[1px] bg-accent/45" />
        <span className="rounded-[1px] bg-accent/45" />
        <span className="rounded-[1px] bg-accent" />
      </div>
      <Item id="map" label="Map" />
      <Item id="assets" label="Assets" />
      <div className="flex-1" />
      <button
        onClick={toggleAssistant}
        title="AI Analyst"
        className={`flex h-11 w-11 items-center justify-center rounded-xl transition ${
          assistantOpen ? "bg-accent/15 text-accent-300" : "text-slate-500 hover:bg-white/5 hover:text-slate-200"
        }`}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-5 w-5">
          <path d="M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5Z" />
        </svg>
      </button>
    </div>
  );
}
