/**
 * Desktop/mobile smoke for the Phase 2A Tutorial Workbench.
 *
 * The API/WebSocket endpoints are mocked via Playwright routing so the suite
 * needs no backend process: HTTP responses mirror app/api/schemas.py and the
 * WebSocket mock streams events shaped like app/api/events.py.
 */
import { expect, test, type Locator } from "@playwright/test";

const THREAD_ID = "00000000-0000-4000-8000-000000000000";

const MARKDOWN = `# Tutorial Research Report

## Findings

Some **bold** content.`;

const FILES = [
  {
    name: "tutorial-report.md",
    path: "tutorial-report.md",
    size: 123,
    media_type: "text/markdown",
  },
  {
    name: "tutorial-report.pdf",
    path: "tutorial-report.pdf",
    size: 456,
    media_type: "application/pdf",
  },
];

/** Event stream pushed over the mocked WebSocket after the task POST. */
const EVENTS = [
  {
    version: 1,
    sequence: 1,
    thread_id: THREAD_ID,
    type: "task_started",
    message: "research aspirin",
    data: {},
    timestamp: "2026-01-01T00:00:00Z",
  },
  {
    version: 1,
    sequence: 2,
    thread_id: THREAD_ID,
    type: "agent_started",
    message: "mock-research-agent started",
    data: { agent_name: "mock-research-agent" },
    timestamp: "2026-01-01T00:00:01Z",
  },
  {
    version: 1,
    sequence: 3,
    thread_id: THREAD_ID,
    type: "tool_started",
    message: "internet_search started",
    data: { tool_name: "internet_search" },
    timestamp: "2026-01-01T00:00:02Z",
  },
  {
    version: 1,
    sequence: 4,
    thread_id: THREAD_ID,
    type: "tool_completed",
    message: "internet_search completed",
    data: { tool_name: "internet_search" },
    timestamp: "2026-01-01T00:00:03Z",
  },
  {
    version: 1,
    sequence: 5,
    thread_id: THREAD_ID,
    type: "artifact_created",
    message: "tutorial-report.md written",
    data: {
      path: "tutorial-report.md",
      name: "tutorial-report.md",
      media_type: "text/markdown",
    },
    timestamp: "2026-01-01T00:00:04Z",
  },
  {
    version: 1,
    sequence: 6,
    thread_id: THREAD_ID,
    type: "task_completed",
    message: "Tutorial run complete",
    data: {},
    timestamp: "2026-01-01T00:00:05Z",
  },
];

/**
 * Event stream for a run that fails inside the provider: the socket pushes
 * work events, then a single task_failed terminal (redacted message).
 */
const FAILURE_EVENTS = [
  {
    version: 1,
    sequence: 1,
    thread_id: THREAD_ID,
    type: "task_started",
    message: "research aspirin",
    data: {},
    timestamp: "2026-01-01T00:00:00Z",
  },
  {
    version: 1,
    sequence: 2,
    thread_id: THREAD_ID,
    type: "agent_started",
    message: "mock-research-agent started",
    data: { agent_name: "mock-research-agent" },
    timestamp: "2026-01-01T00:00:01Z",
  },
  {
    version: 1,
    sequence: 3,
    thread_id: THREAD_ID,
    type: "tool_started",
    message: "internet_search started",
    data: { tool_name: "internet_search" },
    timestamp: "2026-01-01T00:00:02Z",
  },
  {
    version: 1,
    sequence: 4,
    thread_id: THREAD_ID,
    type: "task_failed",
    message: "",
    data: {},
    timestamp: "2026-01-01T00:00:03Z",
  },
];

/**
 * Installs HTTP + WebSocket mocks mirroring the locked backend contract.
 * Returns the mocked socket so tests can push events after the task POST.
 * Supports multi-run scenarios: every task POST and every WebSocket
 * connection is recorded, and pushEventStream(events, runIndex) targets the
 * run-th connection — the same way a re-run after failure/cancel opens a
 * fresh socket and starts a new task.
 */
async function mockBackend(page: import("@playwright/test").Page) {
  const wsRoutes: import("@playwright/test").WebSocketRoute[] = [];
  let taskPostedCount = 0;

  await page.route("**/api/task", (route) => {
    taskPostedCount += 1;
    route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ status: "started", thread_id: THREAD_ID }),
    });
  });
  await page.route("**/api/task/*/cancel", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ thread_id: THREAD_ID, status: "cancelled" }),
    })
  );
  await page.route("**/api/upload", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "uploaded",
        thread_id: THREAD_ID,
        files: [{ name: "constraints.md", size: 7 }],
      }),
    })
  );
  await page.route("**/api/files*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ thread_id: THREAD_ID, files: FILES }),
    })
  );
  await page.route("**/api/download*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/markdown",
      body: MARKDOWN,
    })
  );

  await page.routeWebSocket(/\/ws\/.+/, (ws) => {
    ws.onMessage((message) => {
      const data = JSON.parse(String(message));
      if (data.type === "ping") {
        ws.send(JSON.stringify({ type: "pong" }));
      }
    });
    wsRoutes.push(ws);
  });

  return {
    /** Push an event stream for a specific run (defaults to the first).
     * Mirrors the real server: the socket opens before POST /api/task, so
     * wait for both the task POST and the run-th socket to exist. */
    async pushEventStream(
      events: unknown[] = EVENTS,
      runIndex = 0
    ): Promise<void> {
      await expect
        .poll(() => taskPostedCount, { timeout: 10_000 })
        .toBeGreaterThan(runIndex);
      await expect
        .poll(() => wsRoutes.length, { timeout: 10_000 })
        .toBeGreaterThan(runIndex);
      for (const event of events) {
        wsRoutes[runIndex].send(JSON.stringify(event));
      }
    },
  };
}

/**
 * Asserts the element is fully inside the viewport and has non-zero size,
 * so no control is clipped, off-screen, or collapsed on the small screen.
 * The element is scrolled to the viewport center first: the center scroll is
 * deterministic, while scrollIntoViewIfNeeded performs the minimum scroll
 * and can leave a fractional lower edge (Linux Chromium once measured
 * 844.203125 against a 844px viewport), which fails the strict bounds check
 * below. Centering clamps to the scroll limits, so an element smaller than
 * the viewport always ends up fully visible; clipping or horizontal overflow
 * still fails the bounds checks.
 */
async function expectInViewport(
  locator: Locator,
  viewport: { width: number; height: number }
) {
  await locator.evaluate((el) =>
    el.scrollIntoView({ block: "center", inline: "nearest" })
  );
  const box = await locator.boundingBox();
  expect(box, `expected ${locator} to be laid out`).not.toBeNull();
  expect(box!.width).toBeGreaterThan(0);
  expect(box!.height).toBeGreaterThan(0);
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width);
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height);
}

test("desktop: run a task, follow events, review and preview artifacts", async ({
  page,
  isMobile,
}) => {
  test.skip(isMobile, "desktop-only flow");

  const backend = await mockBackend(page);
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Tutorial Workbench" })
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Event Feed" })
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Artifacts" })
  ).toBeVisible();

  // Upload a constraint file first.
  await page.getByLabel("Constraint files").setInputFiles({
    name: "constraints.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# rules"),
  });
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText("constraints.md")).toBeVisible();

  // Run the task.
  await page.getByLabel("Task query").fill("research aspirin");
  await page.getByRole("button", { name: "Run Task" }).click();
  await expect(page.getByRole("button", { name: "Cancel Task" })).toBeVisible();
  await backend.pushEventStream();

  // Events land in the feed.
  await expect(page.getByText("mock-research-agent started")).toBeVisible();
  await expect(page.getByText("agent_name: mock-research-agent")).toBeVisible();
  await expect(page.getByText("internet_search started")).toBeVisible();
  await expect(page.getByText("Tutorial run complete")).toBeVisible();

  // Terminal state refreshes the artifact list.
  await expect(
    page.getByRole("link", { name: "Download tutorial-report.md" })
  ).toHaveAttribute("href", /path=tutorial-report\.md/);
  await expect(
    page.getByRole("link", { name: "Download tutorial-report.pdf" })
  ).toHaveAttribute("href", /path=tutorial-report\.pdf/);

  // Markdown preview renders.
  await page
    .getByRole("button", { name: "Preview tutorial-report.md" })
    .click();
  await expect(
    page.getByRole("heading", { level: 2, name: "Findings" })
  ).toBeVisible();
  await expect(page.getByText("bold")).toBeVisible();
});

test("desktop: a failed run can be re-run on the same workbench", async ({
  page,
  isMobile,
}) => {
  test.skip(isMobile, "desktop-only flow");

  const backend = await mockBackend(page);
  await page.goto("/");

  await page.getByLabel("Task query").fill("research aspirin");
  await page.getByRole("button", { name: "Run Task" }).click();
  await expect(page.getByRole("button", { name: "Cancel Task" })).toBeVisible();

  // Provider failure terminal arrives over the socket.
  await backend.pushEventStream(FAILURE_EVENTS, 0);
  await expect(page.getByText("Failed")).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel Task" })).toHaveCount(0);

  // The same workbench can Run again: fresh socket, new task, completion.
  await page.getByRole("button", { name: "Run Task" }).click();
  await backend.pushEventStream(EVENTS, 1);
  await expect(page.getByText("Tutorial run complete")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download tutorial-report.md" })
  ).toBeVisible();
});

test("desktop: cancel a running task, then re-run", async ({
  page,
  isMobile,
}) => {
  test.skip(isMobile, "desktop-only flow");

  const backend = await mockBackend(page);
  await page.goto("/");

  await page.getByLabel("Task query").fill("research aspirin");
  await page.getByRole("button", { name: "Run Task" }).click();
  await expect(page.getByRole("button", { name: "Cancel Task" })).toBeVisible();

  // A few work events, no terminal yet — the run is still in flight.
  await backend.pushEventStream(EVENTS.slice(0, 3), 0);

  // User cancels; the cancel endpoint answers cancelled.
  await page.getByRole("button", { name: "Cancel Task" }).click();
  await expect(page.getByText("Cancelled")).toBeVisible();
  await expect(page.getByRole("button", { name: "Run Task" })).toBeVisible();

  // The workbench can Run again after cancel: fresh socket, new task.
  await page.getByRole("button", { name: "Run Task" }).click();
  await backend.pushEventStream(EVENTS, 1);
  await expect(page.getByText("Tutorial run complete")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download tutorial-report.pdf" })
  ).toBeVisible();
});

test("mobile: single-column layout, every control visible, no horizontal overflow", async ({
  page,
  isMobile,
}) => {
  test.skip(!isMobile, "mobile-only layout");

  const VIEWPORT = { width: 390, height: 844 };
  const backend = await mockBackend(page);
  await page.goto("/");

  // Task query input.
  const taskQuery = page.getByLabel("Task query");
  await expect(taskQuery).toBeVisible();
  await expectInViewport(taskQuery, VIEWPORT);

  // Constraint-file input.
  const constraintInput = page.getByLabel("Constraint files");
  await expect(constraintInput).toBeVisible();
  await expectInViewport(constraintInput, VIEWPORT);

  // Upload control.
  const upload = page.getByRole("button", { name: "Upload" });
  await expect(upload).toBeVisible();
  await expectInViewport(upload, VIEWPORT);

  // Run control.
  const run = page.getByRole("button", { name: "Run Task" });
  await expect(run).toBeVisible();
  await expectInViewport(run, VIEWPORT);

  // Event Feed panel.
  const feed = page.locator('section[aria-label="Event feed"]');
  await expect(feed).toBeVisible();
  await expectInViewport(feed, VIEWPORT);

  // Start a run and verify the Cancel control while the task is running.
  await taskQuery.fill("research aspirin");
  await run.click();
  const cancel = page.getByRole("button", { name: "Cancel Task" });
  await expect(cancel).toBeVisible();
  await expectInViewport(cancel, VIEWPORT);

  await backend.pushEventStream();
  await expect(page.getByText("Tutorial run complete")).toBeVisible();

  // Download controls for both artifacts.
  for (const name of ["tutorial-report.md", "tutorial-report.pdf"]) {
    const download = page.getByRole("link", { name: `Download ${name}` });
    await expect(download).toBeVisible();
    await expectInViewport(download, VIEWPORT);
  }

  // Preview control, then the preview pane itself.
  const preview = page.getByRole("button", {
    name: "Preview tutorial-report.md",
  });
  await expect(preview).toBeVisible();
  await expectInViewport(preview, VIEWPORT);
  await preview.click();
  const previewPane = page.locator('section[aria-label="Report preview"]');
  await expect(previewPane).toBeVisible();
  await expectInViewport(previewPane, VIEWPORT);

  // No horizontal overflow at 390px.
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
