import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento, as chamadas /api vão para a API Python (allun servir).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
});
