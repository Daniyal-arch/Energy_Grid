import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // the backend (backend/, `uv run uvicorn app.main:app --port 8080`) behind the dev server, so
  // the Ask tab calls /api on the same origin; the deployed site routes /api through the Worker
  server: {
    proxy: {
      "/api": { target: process.env.VITE_API_PROXY ?? "http://localhost:8080", changeOrigin: true },
    },
  },
});
