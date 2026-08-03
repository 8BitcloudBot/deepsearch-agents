import { defineConfig } from "@playwright/test";

/**
 * E2E smoke for the Tutorial Workbench.
 *
 * The frontend dev server runs on 5173; the Phase 2 API is NOT started here.
 * Every /api/* and /ws/* request is routed to in-test mocks (see
 * e2e/tutorial-workbench.spec.ts), so the suite exercises the real UI against
 * the locked HTTP/WebSocket contract shapes without a backend process.
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  // Vitest is configured (see vitest.config.ts) to exclude ./e2e so the
  // browser tests are only collected by Playwright.
  timeout: 30_000,
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "off",
  },
  webServer: {
    // Corepack-installed pnpm is not on PATH inside the webServer shell, so
    // invoke the local vite binary directly.
    command:
      "./node_modules/.bin/vite dev --port 5173 --strictPort --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: false,
    timeout: 60_000,
  },
  projects: [
    {
      name: "desktop",
      use: { viewport: { width: 1440, height: 900 } },
    },
    {
      name: "mobile",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
