import { defineConfig, configDefaults } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    // Playwright browser tests live in ./e2e; Vitest must not collect them.
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
