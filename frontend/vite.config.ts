import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // brief 30: the map libraries in chunks of their own (cached across deploys of the app code)
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes("node_modules/maplibre-gl")) return "maplibre";
          if (/node_modules\/(@deck\.gl|@luma\.gl|@math\.gl|@loaders\.gl|mjolnir)/.test(id)) return "deckgl";
          if (/node_modules\/(react|react-dom|scheduler)\//.test(id)) return "react";
          return undefined;
        },
      },
    },
  },
  // the backend (backend/, `uv run uvicorn app.main:app --port 8080`) behind the dev server, so
  // the Ask tab calls /api on the same origin; the deployed site routes /api through the Worker
  server: {
    proxy: {
      "/api": { target: process.env.VITE_API_PROXY ?? "http://localhost:8080", changeOrigin: true },
    },
  },
});
