import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    proxy: {
      "/api/user": { target: "http://localhost:8001", changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/user/, "") },
      "/api/item": { target: "http://localhost:8002", changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/item/, "") },
      "/api/notif": { target: "http://localhost:8003", changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/notif/, "") },
    },
  },
});
