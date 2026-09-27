// Video capture mode (?capture=4x5 | ?capture=9x16): the power view on a
// fixed-size stage laid out for LinkedIn's mobile feed. scripts/record-video.mjs
// renders it frame by frame with a virtual clock, so anything animated on this
// page must run on requestAnimationFrame/performance.now (not CSS transitions,
// which would keep real time). See docs/VIDEO.md.

export type CaptureFormat = "4x5" | "9x16";

export const CAPTURE_VIDEO: Record<CaptureFormat, { width: number; height: number }> = {
  "4x5": { width: 1080, height: 1350 }, // tallest the LinkedIn feed shows in-line
  "9x16": { width: 1080, height: 1920 }, // full-screen vertical player
};

export interface CaptureConfig {
  format: CaptureFormat;
  /** device pixels per CSS px; the recorder uses it as deviceScaleFactor */
  scale: number;
  /** stage size in CSS px (video size / scale) */
  width: number;
  height: number;
  /** true when driven by the recorder: wait for window.__captureGo() to start */
  recording: boolean;
}

export function readCapture(search = window.location.search): CaptureConfig | null {
  const params = new URLSearchParams(search);
  const format = params.get("capture");
  if (format !== "4x5" && format !== "9x16") return null;
  const scale = Math.min(3, Math.max(1, Number(params.get("scale")) || 2));
  const video = CAPTURE_VIDEO[format];
  return {
    format,
    scale,
    width: Math.round(video.width / scale),
    height: Math.round(video.height / scale),
    recording: params.has("record"),
  };
}

/** Map padding (CSS px) so Germany and the neighbour labels clear the title card and legend. */
export function capturePadding(c: CaptureConfig): { top: number; bottom: number; left: number; right: number } {
  if (c.format === "9x16") return { top: 270, bottom: 160, left: 14, right: 14 };
  return { top: 112, bottom: 100, left: 14, right: 14 };
}

declare global {
  interface Window {
    /** set by the capture page once its data is in; the recorder waits for it */
    __captureReady?: boolean;
  }
}

