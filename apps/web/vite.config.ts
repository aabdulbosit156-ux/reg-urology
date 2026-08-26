import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import flowbiteReact from "flowbite-react/plugin/vite";
import { defineConfig } from "vite";

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), ...(mode === "test" ? [] : [flowbiteReact()])],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
}));
