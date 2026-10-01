// Records the power-view video stage (?capture=4x5 | 9x16) as an H.264 MP4 for
// LinkedIn and similar feeds.
//
//   npm run record:video                         # 4:5, 20 s, 30 fps
//   npm run record:video -- --format 9x16 --seconds 15
//   npm run record:video -- --poster-only          # just the still, for a quick check
//   npm run record:video -- --format 16x9 --scale 1.25 --seconds 30 --name europe-tour \
//       --url "http://localhost:5173/?europe"      # Europe tour: France, Italy, Poland
//
// Needs the dev server (npm run dev) and the API running. Headless Chrome (or
// Edge; override with CHROME_PATH) renders the page on a VIRTUAL clock: every
// frame advances time by exactly 1/fps and is screenshotted, so the video is
// perfectly smooth no matter how slowly the GPU renders. Frames are encoded
// inside the browser with WebCodecs and written with a small built-in MP4 muxer,
// so no ffmpeg install is needed. A poster PNG (for the LinkedIn thumbnail) is
// saved next to the video.

import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const argv = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : fallback;
};

const FORMATS = { "4x5": [1080, 1350], "9x16": [1080, 1920], "16x9": [1920, 1080] };
const format = arg("format", "4x5");
if (!FORMATS[format]) throw new Error(`--format must be one of ${Object.keys(FORMATS).join(", ")}`);
const scale = Number(arg("scale", "2"));
const fps = Number(arg("fps", "30"));
const seconds = Number(arg("seconds", "20"));
const posterAt = Number(arg("poster-at", "2"));
const posterOnly = argv.includes("--poster-only");
const baseUrl = arg("url", "http://localhost:5173/");
const [videoW, videoH] = FORMATS[format];
const cssW = Math.round(videoW / scale);
const cssH = Math.round(videoH / scale);
const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
const name = arg("name", "power-grid");
const out = path.resolve(arg("out", path.join("..", "recordings", `${name}-${format}-${stamp}.mp4`)));
const frames = Math.round(seconds * fps);

const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
].filter(Boolean);
const chromePath = CHROME_CANDIDATES.find((p) => fs.existsSync(p));
if (!chromePath) throw new Error("Chrome/Edge not found; set CHROME_PATH");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ── virtual clock, installed before any page script runs ──────────────────────
// performance.now/Date.now/requestAnimationFrame all read one clock. During
// warm-up it follows real frames; for recording the recorder steps it.
const VIRTUAL_CLOCK = `(() => {
  const realRaf = window.requestAnimationFrame.bind(window);
  const dateZero = Date.now();
  let now = 0;
  let queue = [];
  let nextId = 1;
  let auto = true;
  let last = null;
  performance.now = () => now;
  Date.now = () => dateZero + now;
  window.requestAnimationFrame = (cb) => {
    const id = nextId++;
    queue.push({ id, cb });
    return id;
  };
  window.cancelAnimationFrame = (id) => {
    queue = queue.filter((entry) => entry.id !== id);
  };
  const flush = () => {
    const due = queue;
    queue = [];
    for (const { cb } of due) {
      try { cb(now); } catch (e) { console.error(e); }
    }
  };
  const pump = (t) => {
    if (!auto) return;
    now += last === null ? 16.7 : Math.min(50, Math.max(0, t - last));
    last = t;
    flush();
    realRaf(pump);
  };
  realRaf(pump);
  window.__vclock = {
    manual() { auto = false; },
    step(ms) { now += ms; flush(); },
    flush,
  };
})();`;

// ── in-page encoder: WebCodecs H.264 + minimal MP4 (ftyp/moov/mdat) muxer ─────
const ENCODER = `(() => {
  const u8 = (a) => new Uint8Array(a);
  const u16 = (v) => [(v >> 8) & 255, v & 255];
  const u32 = (v) => [(v >>> 24) & 255, (v >>> 16) & 255, (v >>> 8) & 255, v & 255];
  const str = (s) => [...s].map((c) => c.charCodeAt(0));
  const cat = (parts) => {
    let n = 0;
    for (const p of parts) n += p.length;
    const o = new Uint8Array(n);
    let at = 0;
    for (const p of parts) { o.set(p, at); at += p.length; }
    return o;
  };
  const box = (type, ...parts) => {
    const body = cat(parts.map((p) => (p instanceof Uint8Array ? p : u8(p))));
    return cat([u8(u32(body.length + 8)), u8(str(type)), body]);
  };
  const full = (type, version, flags, ...parts) =>
    box(type, u8([version, (flags >> 16) & 255, (flags >> 8) & 255, flags & 255]), ...parts);
  const MATRIX = [0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000].flatMap(u32);

  function mux({ width, height, fps, samples, avcC }) {
    const timescale = 90000;
    const delta = Math.round(timescale / fps);
    const n = samples.length;
    const mediaDuration = n * delta;
    const movieDuration = Math.round((n / fps) * 1000);
    const ftyp = box("ftyp", str("isom"), u32(0x200), str("isom"), str("iso2"), str("avc1"), str("mp41"));
    const mvhd = full("mvhd", 0, 0, u32(0), u32(0), u32(1000), u32(movieDuration), u32(0x00010000), u16(0x0100),
      u16(0), u32(0), u32(0), MATRIX, new Array(24).fill(0), u32(2));
    const tkhd = full("tkhd", 0, 3, u32(0), u32(0), u32(1), u32(0), u32(movieDuration), u32(0), u32(0),
      u16(0), u16(0), u16(0), u16(0), MATRIX, u32(width * 65536), u32(height * 65536));
    const mdhd = full("mdhd", 0, 0, u32(0), u32(0), u32(timescale), u32(mediaDuration), u16(0x55c4), u16(0));
    const hdlr = full("hdlr", 0, 0, u32(0), str("vide"), u32(0), u32(0), u32(0), str("VideoHandler"), [0]);
    const vmhd = full("vmhd", 0, 1, u16(0), u16(0), u16(0), u16(0));
    const dinf = box("dinf", full("dref", 0, 0, u32(1), full("url ", 0, 1)));
    const avc1 = box("avc1", [0, 0, 0, 0, 0, 0], u16(1), u16(0), u16(0), u32(0), u32(0), u32(0),
      u16(width), u16(height), u32(0x00480000), u32(0x00480000), u32(0), u16(1), new Array(32).fill(0),
      u16(0x0018), u16(0xffff), box("avcC", avcC));
    const stsd = full("stsd", 0, 0, u32(1), avc1);
    const stts = full("stts", 0, 0, u32(1), u32(n), u32(delta));
    const keys = samples.map((s, i) => (s.key ? i + 1 : 0)).filter(Boolean);
    const stss = full("stss", 0, 0, u32(keys.length), keys.flatMap(u32));
    const stsc = full("stsc", 0, 0, u32(1), u32(1), u32(n), u32(1));
    const stsz = full("stsz", 0, 0, u32(0), u32(n), samples.flatMap((s) => u32(s.data.length)));
    // presentation offsets, only if the encoder reordered frames (B-frames)
    const offsets = samples.map((s, i) => Math.round((s.timestamp / 1e6) * timescale) - i * delta);
    const ctts = offsets.some((o) => o !== 0)
      ? full("ctts", 1, 0, u32(n), samples.flatMap((_, i) => [...u32(1), ...u32(offsets[i])]))
      : null;
    const moov = (mdatStart) => {
      const stco = full("stco", 0, 0, u32(1), u32(mdatStart));
      const tables = [stsd, stts, ...(ctts ? [ctts] : []), stss, stsc, stsz, stco];
      const stbl = box("stbl", ...tables);
      return box("moov", mvhd, box("trak", tkhd, box("mdia", mdhd, hdlr, box("minf", vmhd, dinf, stbl))));
    };
    const moovSize = moov(0).length;
    const payload = cat(samples.map((s) => s.data));
    return cat([
      ftyp,
      moov(ftyp.length + moovSize + 8),
      u8(u32(payload.length + 8)),
      u8(str("mdat")),
      payload,
    ]);
  }

  window.__enc = {
    samples: [],
    avcC: null,
    error: null,
    frames: 0,
    async init({ width, height, fps, bitrate }) {
      const base = { width, height, bitrate, framerate: fps, avc: { format: "avc" }, latencyMode: "quality" };
      const tries = [
        { ...base, codec: "avc1.640032", hardwareAcceleration: "prefer-software" },
        { ...base, codec: "avc1.4d0032", hardwareAcceleration: "prefer-software" },
        { ...base, codec: "avc1.42e032", hardwareAcceleration: "prefer-software" },
        { ...base, codec: "avc1.640032" },
      ];
      let config = null;
      for (const c of tries) {
        if ((await VideoEncoder.isConfigSupported(c)).supported) { config = c; break; }
      }
      if (!config) throw new Error("no supported H.264 encoder config");
      this.encoder = new VideoEncoder({
        output: (chunk, meta) => {
          if (meta?.decoderConfig?.description && !this.avcC) {
            this.avcC = new Uint8Array(meta.decoderConfig.description);
          }
          const data = new Uint8Array(chunk.byteLength);
          chunk.copyTo(data);
          this.samples.push({ data, key: chunk.type === "key", timestamp: chunk.timestamp });
        },
        error: (e) => { this.error = String(e); },
      });
      this.encoder.configure(config);
      this.fps = fps;
      this.width = width;
      this.height = height;
      return config.codec;
    },
    async add(b64) {
      if (this.error) throw new Error(this.error);
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const bitmap = await createImageBitmap(new Blob([bytes], { type: "image/jpeg" }));
      const us = 1e6 / this.fps;
      const frame = new VideoFrame(bitmap, { timestamp: Math.round(this.frames * us), duration: Math.round(us) });
      this.encoder.encode(frame, { keyFrame: this.frames % (this.fps * 2) === 0 });
      frame.close();
      bitmap.close();
      this.frames += 1;
      while (this.encoder.encodeQueueSize > 8) await new Promise((r) => setTimeout(r, 5));
    },
    async finish() {
      await this.encoder.flush();
      if (this.error) throw new Error(this.error);
      this.mp4 = mux({ width: this.width, height: this.height, fps: this.fps, samples: this.samples, avcC: this.avcC });
      return this.mp4.length;
    },
    part(start, size) {
      let s = "";
      const bytes = this.mp4.subarray(start, start + size);
      for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
      return btoa(s);
    },
  };
})();`;

// ── browser + CDP plumbing ────────────────────────────────────────────────────
const port = 9400 + Math.floor(Math.random() * 400);
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "infraatlas-rec-"));
const chrome = spawn(chromePath, [
  "--headless=new",
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`,
  `--window-size=${cssW},${cssH}`,
  "--hide-scrollbars",
  "--ignore-gpu-blocklist",
  "--enable-gpu",
  "--enable-unsafe-swiftshader",
  "--force-color-profile=srgb",
  "--disable-background-timer-throttling",
  "--disable-renderer-backgrounding",
  "--no-first-run",
  "--no-default-browser-check",
  "about:blank",
]);
chrome.stderr.on("data", () => {});

// Chrome answers /json before its first tab exists, so wait for a page target
let page = null;
for (let i = 0; i < 80 && !page; i++) {
  try {
    const targets = await fetch(`http://127.0.0.1:${port}/json`).then((r) => r.json());
    page = targets.find((t) => t.type === "page" && t.webSocketDebuggerUrl) ?? null;
  } catch {
    // not listening yet
  }
  if (!page) await sleep(250);
}
if (!page) throw new Error("could not reach headless Chrome");
const ws = new WebSocket(page.webSocketDebuggerUrl);
let msgId = 0;
const pending = new Map();
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++msgId;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    const p = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) p.reject(new Error(msg.error.message));
    else p.resolve(msg.result);
  } else if (msg.method === "Runtime.exceptionThrown") {
    const d = msg.params.exceptionDetails;
    console.warn("[page]", (d.exception?.description ?? d.text).split("\n")[0]);
  }
};
await new Promise((r) => (ws.onopen = r));
const evaluate = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text);
  return r.result?.value;
};

const cleanup = () => {
  try {
    ws.close();
  } catch {}
  chrome.kill();
  // Chrome can hold files in its temp profile for a moment after exit (EBUSY on
  // Windows): retry a few times, and never fail the run over a temp folder
  const removeProfile = (attempt) => {
    try {
      fs.rmSync(profile, { recursive: true, force: true });
    } catch {
      if (attempt < 5) setTimeout(() => removeProfile(attempt + 1), 1000);
    }
  };
  setTimeout(() => removeProfile(0), 1500);
};

try {
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: cssW, height: cssH, deviceScaleFactor: scale, mobile: false });
  await send("Page.addScriptToEvaluateOnNewDocument", { source: VIRTUAL_CLOCK });
  const url = new URL(baseUrl);
  url.searchParams.set("capture", format);
  url.searchParams.set("scale", String(scale));
  url.searchParams.set("record", "1");
  console.log(`recording ${url.href}`);
  console.log(`${videoW}x${videoH} · ${fps} fps · ${seconds} s (${frames} frames) -> ${out}`);
  await send("Page.navigate", { url: url.href });

  // warm-up: real-time frames until data, map and plants are in (the page may
  // still be navigating on the first polls, so evaluation errors just mean "not yet")
  const t0 = Date.now();
  const isReady = () => evaluate("window.__captureReady === true").catch(() => false);
  while (!(await isReady())) {
    if (Date.now() - t0 > 180_000) throw new Error("page never became ready (is the API running?)");
    await sleep(500);
  }
  console.log(`data ready after ${((Date.now() - t0) / 1000).toFixed(0)} s; settling map tiles…`);
  await sleep(6000);

  const posterPath = out.replace(/\.mp4$/i, "-poster.png");
  fs.mkdirSync(path.dirname(out), { recursive: true });
  if (posterOnly) {
    const png = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(posterPath, Buffer.from(png.data, "base64"));
    console.log(`poster ${posterPath}`);
  } else {
    await recordVideo(posterPath);
  }
} finally {
  cleanup();
}

async function recordVideo(posterPath) {
  const codec = await evaluate(`${ENCODER}; window.__enc.init(${JSON.stringify({ width: videoW, height: videoH, fps, bitrate: 14_000_000 })})`);
  console.log(`encoder: ${codec}`);

  // take over the clock: from here every frame advances time by exactly 1/fps
  // pages with a scripted sequence (the Europe tour) start it on the first recorded frame
  await evaluate("window.__vclock.manual(); window.__captureGo && window.__captureGo(); window.__vclock.flush(); true");
  const dt = 1000 / fps;
  const posterFrame = Math.min(frames - 1, Math.round(posterAt * fps));
  const started = Date.now();
  for (let i = 0; i < frames; i++) {
    await evaluate(`window.__vclock.step(${dt}); new Promise((r) => setTimeout(r, 12))`);
    await evaluate("window.__vclock.flush(); new Promise((r) => setTimeout(r, 4))");
    const shot = await send("Page.captureScreenshot", { format: "jpeg", quality: 94 });
    await evaluate(`window.__enc.add(${JSON.stringify(shot.data)})`);
    if (i === posterFrame) {
      const png = await send("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(posterPath, Buffer.from(png.data, "base64"));
    }
    if (i % fps === 0 || i === frames - 1) {
      const rate = (i + 1) / ((Date.now() - started) / 1000);
      process.stdout.write(`\r  frame ${i + 1}/${frames} · ${rate.toFixed(1)} frames/s   `);
    }
  }
  process.stdout.write("\n");

  const size = await evaluate("window.__enc.finish()");
  const chunks = [];
  const step = 2 * 1024 * 1024;
  for (let at = 0; at < size; at += step) {
    chunks.push(Buffer.from(await evaluate(`window.__enc.part(${at}, ${step})`), "base64"));
  }
  fs.writeFileSync(out, Buffer.concat(chunks));
  console.log(`wrote ${out} (${(size / 1e6).toFixed(1)} MB)`);
  console.log(`poster ${posterPath}`);
}
