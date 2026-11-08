// A card's method and source notes: one quiet line that opens in place (brief 31: the figure
// first; how it was made and where it comes from one click away, never deleted).

import { useState, type ReactNode } from "react";

export function Note({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2 text-[10px] leading-snug text-[#8d94a1]">
      {open && <div>{children}</div>}
      <button onClick={() => setOpen(!open)} aria-expanded={open} className={`text-[#8d94a1] hover:text-slate-200 ${open ? "mt-0.5" : ""}`}>
        {open ? "Less" : "Method ›"}
      </button>
    </div>
  );
}
