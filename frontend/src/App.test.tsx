import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { downloadUrl } from "./lib/api";
import type { TutorialEvent } from "./types";

/** Minimal controllable WebSocket double for jsdom tests. */
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.readyState = 3;
    this.onclose?.();
  }

  open(): void {
    this.readyState = 1;
    this.onopen?.();
  }

  receive(payload: unknown): void {
    this.onmessage?.({
      data: typeof payload === "string" ? payload : JSON.stringify(payload),
    });
  }
}

function makeEvent(
  type: TutorialEvent["type"],
  overrides: Partial<TutorialEvent> = {}
): TutorialEvent {
  return {
    version: 1,
    sequence: 1,
    thread_id: "00000000-0000-4000-8000-000000000000",
    type,
    message: type,
    data: {},
    timestamp: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const MARKDOWN_BODY = `# Tutorial Research Report

## Findings

Some **bold** content.`;

function okJson(body: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

const FILES = [
  { name: "tutorial-report.md", path: "tutorial-report.md", size: 123, media_type: "text/markdown" },
  { name: "tutorial-report.pdf", path: "tutorial-report.pdf", size: 456, media_type: "application/pdf" },
];

describe("Tutorial Workbench UI", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    FakeWebSocket.instances = [];
    fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      if (url.endsWith("/api/upload")) {
        return okJson({
          status: "uploaded",
          thread_id: "t",
          files: [{ name: "constraints.md", size: 7 }],
        });
      }
      if (url.includes("/api/files")) {
        return okJson({ thread_id: "t", files: FILES });
      }
      if (url.includes("/api/download")) {
        return {
          ok: true,
          status: 200,
          text: async () => MARKDOWN_BODY,
        } as Response;
      }
      if (url.includes("/cancel")) {
        return okJson({ thread_id: "t", status: "cancelled" });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  async function startTask(query = "research aspirin") {
    render(<App />);
    fireEvent.change(screen.getByLabelText(/task query/i), {
      target: { value: query },
    });
    fireEvent.click(screen.getByRole("button", { name: /run task/i }));
    const ws = FakeWebSocket.instances[0];
    expect(ws).toBeDefined();
    act(() => ws.open());
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    return ws;
  }

  it("submits the query and renders the task_started message in the feed", async () => {
    const ws = await startTask("research aspirin");

    act(() => ws.receive(makeEvent("task_started", { message: "research aspirin" })));

    await waitFor(() => {
      // The same text is typed into the query textarea, so scope the match
      // to the event feed message.
      expect(
        screen.getByText(/research aspirin/, { selector: ".event-message" })
      ).toBeInTheDocument();
    });
    const taskCall = fetchMock.mock.calls.find((c) =>
      String(c[0]).endsWith("/api/task")
    );
    expect(JSON.parse(String(taskCall![1]!.body))).toMatchObject({
      query: "research aspirin",
    });
  });

  it("renders agent, tool, and artifact event families structurally", async () => {
    const ws = await startTask();
    const tid = "00000000-0000-4000-8000-000000000000";

    act(() => {
      ws.receive(
        makeEvent("agent_started", {
          thread_id: tid,
          sequence: 1,
          data: { agent_name: "mock-research-agent" },
        })
      );
      ws.receive(
        makeEvent("tool_started", {
          thread_id: tid,
          sequence: 2,
          data: { tool_name: "internet_search" },
        })
      );
      ws.receive(
        makeEvent("tool_completed", {
          thread_id: tid,
          sequence: 3,
          data: { tool_name: "internet_search" },
        })
      );
      ws.receive(
        makeEvent("artifact_created", {
          thread_id: tid,
          sequence: 4,
          data: {
            path: "tutorial-report.md",
            name: "tutorial-report.md",
            media_type: "text/markdown",
          },
        })
      );
    });

    await waitFor(() => {
      expect(screen.getByText(/mock-research-agent/)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/internet_search/).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/tutorial-report\.md/)).toBeInTheDocument();
  });

  it("shows cancel only while the task is running", async () => {
    render(<App />);
    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/task query/i), {
      target: { value: "q" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run task/i }));
    const ws = FakeWebSocket.instances[0];
    act(() => ws.open());

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /cancel task/i })
      ).toBeInTheDocument();
    });

    act(() =>
      ws.receive(
        makeEvent("task_completed", { thread_id: "00000000-0000-4000-8000-000000000000" })
      )
    );

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /cancel task/i })
      ).not.toBeInTheDocument();
    });
  });

  it("refreshes and lists artifacts after the terminal event", async () => {
    const ws = await startTask();
    act(() =>
      ws.receive(
        makeEvent("task_completed", { thread_id: "00000000-0000-4000-8000-000000000000" })
      )
    );

    await waitFor(() => {
      expect(screen.getByText(/tutorial-report\.md/)).toBeInTheDocument();
    });
    await waitFor(() => {
      const fileCall = fetchMock.mock.calls.some((c) =>
        String(c[0]).includes("/api/files")
      );
      expect(fileCall).toBe(true);
    });
    expect(
      screen.getByRole("link", { name: /download tutorial-report\.md/i })
    ).toHaveAttribute("href", expect.stringContaining("tutorial-report.md"));
    expect(
      screen.getByRole("link", { name: /download tutorial-report\.pdf/i })
    ).toHaveAttribute("href", expect.stringContaining("tutorial-report.pdf"));
  });

  it("previews the selected Markdown artifact", async () => {
    const ws = await startTask();
    act(() =>
      ws.receive(
        makeEvent("task_completed", { thread_id: "00000000-0000-4000-8000-000000000000" })
      )
    );

    await waitFor(() => {
      expect(screen.getByText(/tutorial-report\.md/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /preview tutorial-report\.md/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { level: 2, name: "Findings" })
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/bold/)).toBeInTheDocument();
  });

  it("encodes artifact names in download URLs", () => {
    const url = downloadUrl("00000000-0000-4000-8000-000000000000", "my report.md");
    expect(url).toBe(
      "http://127.0.0.1:8000/api/download?thread_id=00000000-0000-4000-8000-000000000000&path=my%20report.md"
    );
  });

  it("uploads constraint files before running", async () => {
    render(<App />);
    const file = new File(["# rules"], "constraints.md", {
      type: "text/markdown",
    });
    fireEvent.change(screen.getByLabelText(/constraint files/i), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole("button", { name: /upload/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/constraints\.md/, { selector: "li, span, div" })
      ).toBeInTheDocument();
    });
    const uploadCall = fetchMock.mock.calls.find((c) =>
      String(c[0]).endsWith("/api/upload")
    );
    expect(uploadCall).toBeDefined();
  });

  it("shows an error status when the task fails to start", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/task")) {
        return { ok: false, status: 409, text: async () => "duplicate" } as Response;
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    render(<App />);
    fireEvent.change(screen.getByLabelText(/task query/i), {
      target: { value: "q" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run task/i }));
    const ws = FakeWebSocket.instances[0];
    act(() => ws.open());

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });
});
