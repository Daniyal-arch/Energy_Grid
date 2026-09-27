import fs from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// MVTLayer probes every tile in the viewport, including ones with no data for
// sparse datasets (e.g. the transmission backbone). Vite's SPA fallback would
// otherwise answer those misses with index.html (200, text/html), which
// deck.gl's MVT worker then tries to parse as protobuf and throws on. Force a
// real 404 for missing /tiles/** files so MVTLayer treats them as empty tiles.
function tiles404(): Plugin {
  const handle = (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    if (req.url?.startsWith("/tiles/")) {
      const filePath = path.join(__dirname, "public", req.url.split("?")[0]!);
      if (!fs.existsSync(filePath)) {
        res.statusCode = 404;
        res.end();
        return;
      }
    }
    next();
  };
  return {
    name: "tiles-404",
    configureServer(server) {
      server.middlewares.use(handle);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handle);
    },
  };
}

export default defineConfig({
  plugins: [react(), tiles404()],
});
