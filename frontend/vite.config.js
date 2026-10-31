import { defineConfig } from "vite";

export default defineConfig({
  root: ".",
  server: {
    port: 5173,
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
      "/assets": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});

