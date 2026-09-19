import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy for Member 1's backend. UI calls relative /api/grci so no
// redesign is needed when switching from mock to live backend.
// Run backend on :8000, then `npm run dev` forwards /api -> :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 4173,
  },
});
