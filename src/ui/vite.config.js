import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/color-matches": "http://localhost:8000",
      "/garments": "http://localhost:8000",
      // Exact match only — "/color-palettes/<file>.jpeg" must fall through to
      // Vite's static serving of the public/color-palettes symlink instead.
      "^/color-palettes$": "http://localhost:8000",
    },
  },
});