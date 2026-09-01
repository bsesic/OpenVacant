import { defineConfig } from "vite";
import { resolve } from "path";

// Vite builds the theme assets (Bootstrap SCSS + JS) into Django's static dir.
// django-vite reads the generated manifest and emits the right tags per env.
export default defineConfig({
  base: "/static/dist/",
  build: {
    manifest: true,
    emptyOutDir: true,
    outDir: resolve(__dirname, "../backend/static/dist"),
    rollupOptions: {
      input: resolve(__dirname, "src/main.js"),
    },
  },
  server: {
    origin: "http://localhost:5173",
  },
});
