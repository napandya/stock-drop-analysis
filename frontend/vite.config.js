import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During `npm run dev`, Vite serves the UI on :5173 and proxies API calls to the
// FastAPI backend on :8000, so the frontend talks to "/api/..." in both dev and
// production. `npm run build` emits a static bundle into dist/, which FastAPI
// serves directly for presentations (single origin, no proxy needed).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
