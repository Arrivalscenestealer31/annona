import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// UI is served by the runner's FastAPI on http://127.0.0.1:7070.
// `npm run dev` is for local frontend iteration only.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
  },
  server: {
    port: 5173,
  },
});
