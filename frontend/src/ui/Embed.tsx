// Embeds (brief 30 Track 6.4, docs/product/embeds.md): the iframe code for the view on screen,
// and the credit line an embedded map shows instead of the panels.

import { useState } from "react";

import { CREDITS } from "./sources";

/** The current address with embed=1 set (or removed). */
export function urlWith(embed: boolean): string {
  const u = new URL(window.location.href);
  if (embed) u.searchParams.set("embed", "1");
  else u.searchParams.delete("embed");
  return u.toString();
}

export const embedSnippet = () => `<iframe src="${urlWith(true)}" width="800" height="500" style="border:0" loading="lazy"></iframe>`;

/** "Embed this view": a copyable iframe snippet for the current URL (in the Dashboards menu). */
export function EmbedCode() {
  const [code, setCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  return (
    <div className="mt-1 border-t border-white/[0.07] px-1.5 pt-1.5">
      <button
        onClick={() => {
          setCode(code ? null : embedSnippet());
          setCopied(false);
        }}
        className="w-full rounded-md px-1.5 py-1 text-left text-[11.5px] text-slate-300 hover:bg-white/[0.07]"
        title="Code to show this view in another page (map, key and sources; no panels)"
        aria-expanded={!!code}
      >
        ⧉ Embed this view
      </button>
      {code && (
        <div className="px-1.5 pb-1">
          <textarea
            readOnly
            value={code}
            onFocus={(e) => e.currentTarget.select()}
            rows={4}
            className="mt-1 w-full resize-none rounded-md border border-white/10 bg-black/40 p-1.5 font-mono text-[10px] leading-snug text-slate-200 outline-none"
            aria-label="Embed code"
          />
          <div className="mt-1 flex items-center gap-2">
            <button
              onClick={() => {
                void navigator.clipboard?.writeText(code).then(() => setCopied(true), () => setCopied(false));
              }}
              className="rounded-md border border-white/10 px-2 py-0.5 text-[11px] text-slate-200 hover:bg-white/[0.07]"
            >
              {copied ? "Copied" : "Copy"}
            </button>
            <span className="text-[10px] text-[#8d94a1]">the view as it is now: layers, area, camera</span>
          </div>
        </div>
      )}
    </div>
  );
}

/** The embedded map's credit line: the sources and a way out to the full app. */
export function EmbedCredit() {
  return (
    <div className="absolute inset-x-2 bottom-1.5 z-20 flex items-end gap-3 text-[8.5px] leading-tight text-slate-500">
      <span className="pointer-events-none min-w-0 flex-1 truncate" title={CREDITS}>
        {CREDITS}
      </span>
      <a
        href={urlWith(false)}
        onMouseDown={(e) => (e.currentTarget.href = urlWith(false))}
        onFocus={(e) => (e.currentTarget.href = urlWith(false))}
        target="_blank"
        rel="noopener"
        className="shrink-0 rounded-md border border-white/10 bg-[#0b0f16]/90 px-2 py-1 text-[10.5px] text-slate-200 hover:bg-white/[0.08]"
      >
        Open in InfraAtlas ↗
      </a>
    </div>
  );
}
