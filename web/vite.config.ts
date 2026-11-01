import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import wasm from "vite-plugin-wasm";
import path from "node:path";

const apiTarget = process.env.DEMODOCTOR_API_URL || "http://127.0.0.1:8765";

export default defineConfig({
  // Modern browsers support top-level await; avoid vite-plugin-top-level-await
  // which currently breaks Vite 7 production builds with SWC.
  plugins: [wasm(), react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    target: "esnext",
  },
  server: {
    proxy: {
      "/api": apiTarget,
      "/live-data": apiTarget,
    },
    fs: {
      // Allow serving BotFails MP4 from the repo eval_videos tree (not vendored).
      allow: [path.resolve(__dirname, "..")],
    },
    watch: {
      // Large .rrd binaries lock on Windows and crash Vite's FSWatcher (EBUSY).
      ignored: ["**/public/recordings/**", "**/public/rerun/**"],
    },
    // Soft isolation: CORP on responses so Wasm + large .rrd fetches succeed.
    // Avoid COEP require-corp alone — it blocks same-origin assets missing CORP.
    headers: {
      "Cross-Origin-Resource-Policy": "same-origin",
    },
  },
  preview: {
    proxy: {
      "/api": apiTarget,
      "/live-data": apiTarget,
    },
    headers: {
      "Cross-Origin-Resource-Policy": "same-origin",
    },
  },
  optimizeDeps: {
    exclude: ["@rerun-io/web-viewer", "@rerun-io/web-viewer-react"],
  },
});
