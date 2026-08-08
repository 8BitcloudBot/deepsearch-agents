import { beforeEach, afterEach, describe, it, expect, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import App from "./App";
import { useWorkbench } from "./workbench/useWorkbench";
import {
  downloadUrl,
  getCitations,
  parseCitationsReport,
  parseEvent,
  requestJson,
} from "./workbench/api";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

const HEALTH_PAYLOAD = {
  status: "ok",
  service: "research-copilot-api",
  phase: "2",
  tutorial_profile: "tutorial",
  tutorial_runtime: "mock",
  web_provider: "mock",
  catalog_provider: "mock",
  knowledge_provider: "mock",
};

/** Recording WebSocket double: construction and close are observable. */
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  closed = false;
  onopen: (() => void) | null = null;
  onclose: ((event: unknown) => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: unknown) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  close(): void {
    this.closed = true;
  }
}

function stubHealthResponse(payload: unknown = HEALTH_PAYLOAD) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    )
  );
}

/** JSON response double for the stubbed fetch router. */
function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * URL-suffix fetch router: every request whose URL ends with a route key gets
 * that handler; anything else falls back to the health payload.
 */
function stubFetch(
  routes: Record<string, () => Response | Promise<Response>>
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((input: unknown) => {
    const url = String(input);
    const match = Object.entries(routes).find(([fragment]) =>
      url.endsWith(fragment)
    );
    return Promise.resolve(match ? match[1]() : jsonResponse(HEALTH_PAYLOAD));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function constraintFile(): File {
  return new File(["constraint content"], "constraints.md", {
    type: "text/markdown",
  });
}

function currentThreadId(): string {
  const node = screen.getByText(UUID_PATTERN);
  return node.textContent ?? "";
}

/** Valid TutorialEvent v1 payload builder for WS frames. */
function makeEvent(overrides: Record<string, unknown> = {}) {
  return {
    version: 1,
    sequence: 1,
    thread_id: crypto.randomUUID(),
    type: "task_started",
    message: "Task event",
    data: {},
    timestamp: "2026-08-06T12:00:00Z",
    ...overrides,
  };
}

function openSocket(index = 0) {
  act(() => {
    FakeWebSocket.instances[index].onopen?.();
  });
}

function deliverMessage(text: string, index = 0) {
  act(() => {
    FakeWebSocket.instances[index].onmessage?.({ data: text });
  });
}

function closeSocket(code: number, index = 0) {
  act(() => {
    FakeWebSocket.instances[index].onclose?.({ code });
  });
}

function fireSocketError(index = 0) {
  act(() => {
    FakeWebSocket.instances[index].onerror?.();
  });
}

/** Render the app, upload a constraint, start a task and reach `running`. */
async function startAppRun(): Promise<string> {
  render(<App />);
  await screen.findByText(/Runtime: mock/i);
  openSocket();
  const threadId = currentThreadId();
  stubFetch({
    "/api/upload": () =>
      jsonResponse({
        status: "uploaded",
        thread_id: threadId,
        files: [{ name: "constraints.md", size: 18 }],
      }),
    "/api/task": () =>
      jsonResponse({ status: "started", thread_id: threadId }, 202),
  });
  fireEvent.change(screen.getByLabelText(/constraint file/i), {
    target: { files: [constraintFile()] },
  });
  fireEvent.click(screen.getByRole("button", { name: "Upload" }));
  await screen.findByText(/Uploaded: constraints\.md/i);
  fireEvent.change(screen.getByLabelText(/research query/i), {
    target: { value: "Compare renewable policies" },
  });
  fireEvent.click(screen.getByRole("button", { name: /start research/i }));
  await waitFor(() =>
    expect(
      vi.mocked(fetch).mock.calls.some(([input]) =>
        String(input).endsWith("/api/task")
      )
    ).toBe(true)
  );
  deliverMessage(
    JSON.stringify(
      makeEvent({ thread_id: threadId, sequence: 1, type: "task_started" })
    )
  );
  await screen.findByText(/Status: Running/i);
  return threadId;
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  stubHealthResponse();
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App workbench shell", () => {
  it("renders the project heading", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    expect(
      screen.getByRole("heading", {
        name: /Agent Engineering Research Copilot/i,
      })
    ).toBeInTheDocument();
  });

  it("renders a generated UUID thread label for the active session", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    expect(currentThreadId()).toMatch(UUID_PATTERN);
  });

  it("shows provider and runtime modes from /health", async () => {
    stubHealthResponse({
      ...HEALTH_PAYLOAD,
      tutorial_runtime: "mock",
      web_provider: "mock",
      catalog_provider: "mock",
      knowledge_provider: "mock",
    });
    render(<App />);
    expect(await screen.findByText(/Runtime: mock/i)).toBeInTheDocument();
    expect(screen.getByText(/Web: mock/i)).toBeInTheDocument();
    expect(screen.getByText(/Catalog: mock/i)).toBeInTheDocument();
    expect(screen.getByText(/Knowledge: mock/i)).toBeInTheDocument();
  });

  it("keeps start disabled until a query, an accepted upload and an open WebSocket are present", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    const start = screen.getByRole("button", { name: /start research/i });
    const cancel = screen.getByRole("button", { name: /cancel/i });
    expect(start).toBeDisabled();
    expect(cancel).toBeDisabled();

    const threadId = currentThreadId();
    stubFetch({
      "/api/upload": () =>
        jsonResponse({
          status: "uploaded",
          thread_id: threadId,
          files: [{ name: "constraints.md", size: 18 }],
        }),
    });

    fireEvent.change(screen.getByLabelText(/research query/i), {
      target: { value: "   " },
    });
    expect(start).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/research query/i), {
      target: { value: "Compare renewable policies" },
    });
    expect(start).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/constraint file/i), {
      target: { files: [constraintFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    await screen.findByText(/Status: Ready/i);
    expect(
      screen.getByText(/Uploaded: constraints\.md \(18 bytes\)/i)
    ).toBeInTheDocument();
    // The socket is still connecting, so start stays disabled.
    expect(start).toBeDisabled();

    openSocket();
    expect(start).toBeEnabled();

    fireEvent.change(screen.getByLabelText(/research query/i), {
      target: { value: "" },
    });
    expect(start).toBeDisabled();
  });

  it("new session replaces the UUID and clears query, file, run and artifact state", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    const firstThreadId = currentThreadId();
    stubFetch({
      "/api/upload": () =>
        jsonResponse({
          status: "uploaded",
          thread_id: firstThreadId,
          files: [{ name: "constraints.md", size: 18 }],
        }),
    });

    fireEvent.change(screen.getByLabelText(/research query/i), {
      target: { value: "Renewable energy" },
    });
    fireEvent.change(screen.getByLabelText(/constraint file/i), {
      target: { files: [constraintFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    await screen.findByText(/Uploaded: constraints\.md \(18 bytes\)/i);

    fireEvent.click(screen.getByRole("button", { name: /new session/i }));

    expect(currentThreadId()).not.toBe(firstThreadId);
    expect(currentThreadId()).toMatch(UUID_PATTERN);
    expect(screen.getByLabelText(/research query/i)).toHaveValue("");
    expect(screen.getByText(/No file uploaded/i)).toBeInTheDocument();
    expect(screen.getByText(/Status: Idle/i)).toBeInTheDocument();
    expect(screen.getByText(/No events yet/i)).toBeInTheDocument();
    expect(screen.getByText(/No artifacts yet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start research/i })).toBeDisabled();
  });

  it("connects a WebSocket for the active thread and reconnects on new session", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    const threadId = currentThreadId();
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toContain(`/ws/${threadId}`);
    expect(screen.getByText(/Connection: connecting/i)).toBeInTheDocument();

    act(() => {
      FakeWebSocket.instances[0].onopen?.();
    });
    expect(screen.getByText(/Connection: open/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /new session/i }));
    const nextThreadId = currentThreadId();
    expect(nextThreadId).not.toBe(threadId);
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[0].closed).toBe(true);
    expect(FakeWebSocket.instances[1].url).toContain(`/ws/${nextThreadId}`);
  });
});

describe("useWorkbench session state", () => {
  it("exposes the run state fields in their initial empty form", async () => {
    const { result } = renderHook(() =>
      useWorkbench("http://127.0.0.1:8000")
    );
    await waitFor(() =>
      expect(result.current.health?.tutorial_runtime).toBe("mock")
    );
    expect(result.current.threadId).toMatch(UUID_PATTERN);
    expect(result.current.status).toBe("idle");
    expect(result.current.error).toBeNull();
    expect(result.current.uploadedFile).toBeNull();
    expect(result.current.events).toEqual([]);
    expect(result.current.terminalEvent).toBeNull();
    expect(result.current.files).toEqual([]);
    expect(result.current.markdown).toBeNull();
  });

  it("newSession replaces the UUID and clears query, file, terminal, error and artifact state", async () => {
    const { result } = renderHook(() =>
      useWorkbench("http://127.0.0.1:8000")
    );
    await waitFor(() =>
      expect(result.current.health?.tutorial_runtime).toBe("mock")
    );
    const firstThreadId = result.current.threadId;
    stubFetch({
      "/api/upload": () =>
        jsonResponse({
          status: "uploaded",
          thread_id: firstThreadId,
          files: [{ name: "constraints.md", size: 18 }],
        }),
    });

    act(() => {
      result.current.setQuery("Compare policies");
      result.current.selectFile(constraintFile());
    });
    act(() => {
      result.current.upload();
    });
    await waitFor(() =>
      expect(result.current.uploadedFile).toEqual({
        name: "constraints.md",
        size: 18,
      })
    );
    expect(result.current.status).toBe("ready");

    act(() => {
      result.current.newSession();
    });

    expect(result.current.threadId).not.toBe(firstThreadId);
    expect(result.current.query).toBe("");
    expect(result.current.selectedFile).toBeNull();
    expect(result.current.uploadedFile).toBeNull();
    expect(result.current.status).toBe("idle");
    expect(result.current.error).toBeNull();
    expect(result.current.events).toEqual([]);
    expect(result.current.terminalEvent).toBeNull();
    expect(result.current.files).toEqual([]);
    expect(result.current.markdown).toBeNull();
  });

  it("submit does nothing without an open WebSocket", async () => {
    const { result } = renderHook(() =>
      useWorkbench("http://127.0.0.1:8000")
    );
    await waitFor(() =>
      expect(result.current.health?.tutorial_runtime).toBe("mock")
    );
    const threadId = result.current.threadId;
    const fetchMock = stubFetch({
      "/api/upload": () =>
        jsonResponse({
          status: "uploaded",
          thread_id: threadId,
          files: [{ name: "constraints.md", size: 18 }],
        }),
    });

    act(() => {
      result.current.selectFile(constraintFile());
    });
    act(() => {
      result.current.upload();
    });
    await waitFor(() => expect(result.current.uploadedFile).not.toBeNull());
    act(() => {
      result.current.setQuery("Compare policies");
    });
    act(() => {
      result.current.submit();
    });
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).endsWith("/api/task")
      )
    ).toBe(false);
  });
});

describe("workbench upload", () => {
  it("posts the selected constraint file with the current UUID and shows the accepted filename/size", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    const threadId = currentThreadId();
    const fetchMock = stubFetch({
      "/api/upload": () =>
        jsonResponse({
          status: "uploaded",
          thread_id: threadId,
          files: [{ name: "constraints.md", size: 2048 }],
        }),
    });

    fireEvent.change(screen.getByLabelText(/constraint file/i), {
      target: { files: [constraintFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).endsWith("/api/upload")
        )
      ).toBe(true)
    );
    const uploadCall = fetchMock.mock.calls.find(([input]) =>
      String(input).endsWith("/api/upload")
    );
    expect(uploadCall?.[1]).toMatchObject({ method: "POST" });
    const body = uploadCall?.[1]?.body as FormData;
    expect(body.get("thread_id")).toBe(threadId);
    expect(body.get("files")).toBeInstanceOf(File);

    // The displayed filename/size come from the backend response, not the local File.
    expect(
      await screen.findByText(/Uploaded: constraints\.md \(2048 bytes\)/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Status: Ready/i)).toBeInTheDocument();
  });

  it("shows uploading during the request before becoming ready", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    let resolveUpload: (response: Response) => void = () => undefined;
    const pending = new Promise<Response>((resolve) => {
      resolveUpload = resolve;
    });
    stubFetch({ "/api/upload": () => pending });

    fireEvent.change(screen.getByLabelText(/constraint file/i), {
      target: { files: [constraintFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));

    expect(screen.getByText(/Status: Uploading/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /start research/i })
    ).toBeDisabled();

    await act(async () => {
      resolveUpload(
        jsonResponse({
          status: "uploaded",
          thread_id: "",
          files: [{ name: "constraints.md", size: 18 }],
        })
      );
    });
    await screen.findByText(/Status: Ready/i);
    expect(
      screen.getByText(/Uploaded: constraints\.md \(18 bytes\)/i)
    ).toBeInTheDocument();
  });

  it("shows stable HTTP status/detail on rejection and keeps start disabled", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    stubFetch({
      "/api/upload": () => jsonResponse({ detail: "file too large" }, 413),
    });

    fireEvent.change(screen.getByLabelText(/constraint file/i), {
      target: { files: [constraintFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));

    expect(
      await screen.findByText(/HTTP 413: file too large/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/No file uploaded/i)).toBeInTheDocument();
    expect(screen.getByText(/Status: Idle/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /start research/i })
    ).toBeDisabled();
  });

  it("clears a prior accepted upload when a later upload is rejected", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    const threadId = currentThreadId();
    stubFetch({
      "/api/upload": () =>
        jsonResponse({
          status: "uploaded",
          thread_id: threadId,
          files: [{ name: "constraints.md", size: 18 }],
        }),
    });

    fireEvent.change(screen.getByLabelText(/constraint file/i), {
      target: { files: [constraintFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    await screen.findByText(/Uploaded: constraints\.md \(18 bytes\)/i);

    stubFetch({
      "/api/upload": () => jsonResponse({ detail: "rejected" }, 400),
    });
    fireEvent.change(screen.getByLabelText(/constraint file/i), {
      target: { files: [constraintFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));

    expect(await screen.findByText(/HTTP 400: rejected/i)).toBeInTheDocument();
    expect(screen.getByText(/No file uploaded/i)).toBeInTheDocument();
    expect(screen.getByText(/Status: Idle/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /start research/i })
    ).toBeDisabled();
  });

  it("disables upload while the upload request is pending and re-enables afterwards", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    let resolveUpload: (response: Response) => void = () => undefined;
    const pending = new Promise<Response>((resolve) => {
      resolveUpload = resolve;
    });
    stubFetch({ "/api/upload": () => pending });
    const uploadButton = screen.getByRole("button", { name: "Upload" });

    fireEvent.change(screen.getByLabelText(/constraint file/i), {
      target: { files: [constraintFile()] },
    });
    expect(uploadButton).toBeEnabled();
    fireEvent.click(uploadButton);
    expect(uploadButton).toBeDisabled();

    await act(async () => {
      resolveUpload(
        jsonResponse({
          status: "uploaded",
          thread_id: currentThreadId(),
          files: [{ name: "constraints.md", size: 18 }],
        })
      );
    });
    await screen.findByText(/Status: Ready/i);
    expect(uploadButton).toBeEnabled();
  });

  it("disables upload while a task is running", async () => {
    await startAppRun();

    expect(screen.getByRole("button", { name: "Upload" })).toBeDisabled();
  });
});

describe("task start", () => {
  it("starts the task with the current UUID and the trimmed query", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    openSocket();
    const threadId = currentThreadId();
    const fetchMock = stubFetch({
      "/api/upload": () =>
        jsonResponse({
          status: "uploaded",
          thread_id: threadId,
          files: [{ name: "constraints.md", size: 18 }],
        }),
      "/api/task": () =>
        jsonResponse({ status: "started", thread_id: threadId }, 202),
    });

    fireEvent.change(screen.getByLabelText(/constraint file/i), {
      target: { files: [constraintFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    await screen.findByText(/Status: Ready/i);

    fireEvent.change(screen.getByLabelText(/research query/i), {
      target: { value: "  Compare renewable policies  " },
    });
    fireEvent.click(screen.getByRole("button", { name: /start research/i }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).endsWith("/api/task")
        )
      ).toBe(true)
    );
    const taskCall = fetchMock.mock.calls.find(([input]) =>
      String(input).endsWith("/api/task")
    );
    expect(String(taskCall?.[0])).toBe("http://127.0.0.1:8000/api/task");
    expect(taskCall?.[1]).toMatchObject({ method: "POST" });
    expect(JSON.parse(String(taskCall?.[1]?.body))).toEqual({
      query: "Compare renewable policies",
      thread_id: threadId,
    });

    deliverMessage(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 1, type: "task_started" })
      )
    );
    expect(screen.getByText(/Status: Running/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /start research/i })
    ).toBeDisabled();
  });

  it("a duplicate start failure is visible and does not infer success", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    openSocket();
    const threadId = currentThreadId();
    stubFetch({
      "/api/upload": () =>
        jsonResponse({
          status: "uploaded",
          thread_id: threadId,
          files: [{ name: "constraints.md", size: 18 }],
        }),
      "/api/task": () => jsonResponse({ detail: "task already active" }, 409),
    });

    fireEvent.change(screen.getByLabelText(/constraint file/i), {
      target: { files: [constraintFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    await screen.findByText(/Status: Ready/i);
    fireEvent.change(screen.getByLabelText(/research query/i), {
      target: { value: "Compare renewable policies" },
    });
    fireEvent.click(screen.getByRole("button", { name: /start research/i }));

    expect(
      await screen.findByText(/HTTP 409: task already active/i)
    ).toBeInTheDocument();
    expect(screen.queryByText(/Status: Running/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Status: Success/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Status: Ready/i)).toBeInTheDocument();
    expect(screen.getByText(/No events yet/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /cancel/i })
    ).toBeDisabled();
  });

  it("a new run clears the previous terminal, error and artifact display before submission", async () => {
    const threadId = await startAppRun();
    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 2,
          type: "task_completed",
          message: "Report done",
        })
      )
    );
    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();

    // The start POST resolves asynchronously; await its promise chain
    // (`.finally` clearing taskStartPending) inside act so no update escapes.
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /start research/i }));
    });

    expect(screen.getByText(/Status: Ready/i)).toBeInTheDocument();
    expect(screen.queryByText(/Status: Success/i)).not.toBeInTheDocument();
    expect(screen.getByText(/No events yet/i)).toBeInTheDocument();
    expect(screen.getByText(/No artifacts yet/i)).toBeInTheDocument();

    deliverMessage(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 1, type: "task_started" })
      )
    );
    expect(screen.getByText(/Status: Running/i)).toBeInTheDocument();
  });

  it("disables start immediately while the task POST is pending and prevents a second POST", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    openSocket();
    const threadId = currentThreadId();
    let resolveTask: (response: Response) => void = () => undefined;
    const pending = new Promise<Response>((resolve) => {
      resolveTask = resolve;
    });
    const fetchMock = stubFetch({
      "/api/upload": () =>
        jsonResponse({
          status: "uploaded",
          thread_id: threadId,
          files: [{ name: "constraints.md", size: 18 }],
        }),
      "/api/task": () => pending,
    });

    fireEvent.change(screen.getByLabelText(/constraint file/i), {
      target: { files: [constraintFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    await screen.findByText(/Status: Ready/i);
    fireEvent.change(screen.getByLabelText(/research query/i), {
      target: { value: "Compare renewable policies" },
    });
    const start = screen.getByRole("button", { name: /start research/i });
    expect(start).toBeEnabled();

    fireEvent.click(start);
    expect(start).toBeDisabled();
    // A second click on the disabled button cannot fire a second POST.
    fireEvent.click(start);

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).endsWith("/api/task")
        )
      ).toBe(true)
    );
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).endsWith("/api/task")
      )
    ).toHaveLength(1);

    await act(async () => {
      resolveTask(jsonResponse({ status: "started", thread_id: threadId }, 202));
    });
    deliverMessage(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 1, type: "task_started" })
      )
    );
    expect(screen.getByText(/Status: Running/i)).toBeInTheDocument();
  });

  it("re-enables start on task POST failure while staying ready with the stable error", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    openSocket();
    const threadId = currentThreadId();
    let resolveTask: (response: Response) => void = () => undefined;
    const pending = new Promise<Response>((resolve) => {
      resolveTask = resolve;
    });
    stubFetch({
      "/api/upload": () =>
        jsonResponse({
          status: "uploaded",
          thread_id: threadId,
          files: [{ name: "constraints.md", size: 18 }],
        }),
      "/api/task": () => pending,
    });

    fireEvent.change(screen.getByLabelText(/constraint file/i), {
      target: { files: [constraintFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    await screen.findByText(/Status: Ready/i);
    fireEvent.change(screen.getByLabelText(/research query/i), {
      target: { value: "Compare renewable policies" },
    });
    const start = screen.getByRole("button", { name: /start research/i });

    fireEvent.click(start);
    expect(start).toBeDisabled();

    await act(async () => {
      resolveTask(jsonResponse({ detail: "busy" }, 503));
    });
    expect(await screen.findByText(/HTTP 503: busy/i)).toBeInTheDocument();
    expect(screen.getByText(/Status: Ready/i)).toBeInTheDocument();
    expect(start).toBeEnabled();
  });
});

describe("cancellation", () => {
  it("cancels the active task with the current UUID and becomes cancelled only after the event", async () => {
    const threadId = await startAppRun();
    const fetchMock = stubFetch({
      "/cancel": () =>
        jsonResponse({ thread_id: threadId, status: "cancelling" }, 202),
    });

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) => String(input).endsWith("/cancel"))
      ).toBe(true)
    );
    const cancelCall = fetchMock.mock.calls.find(([input]) =>
      String(input).endsWith("/cancel")
    );
    expect(String(cancelCall?.[0])).toBe(
      `http://127.0.0.1:8000/api/task/${threadId}/cancel`
    );
    expect(cancelCall?.[1]).toMatchObject({ method: "POST" });

    // The UI stays running until the task_cancelled event arrives.
    expect(screen.getByText(/Status: Running/i)).toBeInTheDocument();

    deliverMessage(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 2, type: "task_cancelled" })
      )
    );
    expect(screen.getByText(/Status: Cancelled/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /cancel/i })
    ).toBeDisabled();
  });

  it("cancel 404 shows the stable no-active-task error and does not mark cancelled", async () => {
    await startAppRun();
    stubFetch({
      "/cancel": () => jsonResponse({ detail: "task not found" }, 404),
    });

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(
      await screen.findByText(/HTTP 404: task not found/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Status: Running/i)).toBeInTheDocument();
    expect(screen.queryByText(/Status: Cancelled/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /cancel/i })
    ).toBeEnabled();
  });
});

describe("WebSocket event timeline", () => {
  it("ignores pong heartbeat frames", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    openSocket();

    deliverMessage(JSON.stringify({ type: "pong" }));

    expect(screen.getByText(/No events yet/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/Received a malformed event payload/i)
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Status: Idle/i)).toBeInTheDocument();
  });

  it("shows a safe client error for malformed JSON without inferring success", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    openSocket();

    deliverMessage("{not-json");

    expect(
      screen.getByText(/Received a malformed event payload\./i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Status: Idle/i)).toBeInTheDocument();
    expect(screen.queryByText(/Status: Success/i)).not.toBeInTheDocument();
    expect(screen.getByText(/No events yet/i)).toBeInTheDocument();
  });

  it("rejects unknown event versions with a safe client error", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    openSocket();
    const threadId = currentThreadId();

    deliverMessage(
      JSON.stringify(makeEvent({ thread_id: threadId, version: 99 }))
    );

    expect(
      screen.getByText(/Received an unsupported event version\./i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Status: Idle/i)).toBeInTheDocument();
  });

  it("ignores events for another thread", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    openSocket();

    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: crypto.randomUUID(),
          type: "task_completed",
          message: "foreign completion",
        })
      )
    );

    expect(screen.getByText(/No events yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/foreign completion/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Status: Success/i)).not.toBeInTheDocument();
  });

  it("deduplicates by thread and sequence and sorts ascending", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    openSocket();
    const threadId = currentThreadId();

    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 3,
          type: "tool_started",
          message: "third",
        })
      )
    );
    deliverMessage(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 1, type: "task_started" })
      )
    );
    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 2,
          type: "agent_started",
          message: "second",
        })
      )
    );
    deliverMessage(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 1, type: "task_started" })
      )
    );

    const sequences = screen
      .getAllByText(/^#\d+$/)
      .map((node) => node.textContent);
    expect(sequences).toEqual(["#1", "#2", "#3"]);
    expect(screen.getAllByText(/^#\d+$/)).toHaveLength(3);
  });

  it("retains every task, agent, tool and artifact event type", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    openSocket();
    const threadId = currentThreadId();
    const types = [
      "task_started",
      "agent_started",
      "agent_completed",
      "tool_started",
      "tool_completed",
      "artifact_created",
      "task_completed",
    ];

    types.forEach((type, index) => {
      deliverMessage(
        JSON.stringify(
          makeEvent({
            thread_id: threadId,
            sequence: index + 1,
            type,
            message: `message for ${type}`,
          })
        )
      );
    });

    types.forEach((type) => {
      expect(screen.getByText(type)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/^#\d+$/)).toHaveLength(7);
    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();
    // Flush the post-terminal artifact refresh so its state settles inside act.
    await act(async () => {});
  });

  it("renders sequence, timestamp, type, message and JSON data for each event", async () => {
    render(<App />);
    await screen.findByText(/Runtime: mock/i);
    openSocket();
    const threadId = currentThreadId();

    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 4,
          type: "artifact_created",
          message: "Report markdown written",
          data: { path: "tutorial-report.md", size: 2048 },
        })
      )
    );

    expect(screen.getByText("#4")).toBeInTheDocument();
    expect(screen.getByText("artifact_created")).toBeInTheDocument();
    expect(screen.getByText(/Report markdown written/i)).toBeInTheDocument();
    expect(
      screen.getByText(/"path": "tutorial-report\.md"/)
    ).toBeInTheDocument();
    expect(screen.getByText(/"size": 2048/)).toBeInTheDocument();
    const time = document.querySelector(".event-time");
    expect(time?.textContent).toMatch(/\d{1,2}:\d{2}/);
  });
});

describe("run lifecycle and terminal states", () => {
  it("task_started moves the run to running and enables cancel", async () => {
    const threadId = await startAppRun();
    expect(threadId).toMatch(UUID_PATTERN);
    expect(
      screen.getByRole("button", { name: /cancel/i })
    ).toBeEnabled();
  });

  it("the first terminal event wins and later events cannot change it", async () => {
    const threadId = await startAppRun();

    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 2,
          type: "task_completed",
          message: "accepted completion",
        })
      )
    );
    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();
    // Flush the post-terminal artifact refresh so its state settles inside act.
    await act(async () => {});

    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 3,
          type: "task_failed",
          message: "late failure",
        })
      )
    );

    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();
    expect(screen.queryByText(/Status: Failed/i)).not.toBeInTheDocument();
    // The later event stays visible in the timeline.
    expect(screen.getByText(/late failure/i)).toBeInTheDocument();
  });

  it("malformed frames while running keep the run running", async () => {
    await startAppRun();

    deliverMessage("not-json");

    expect(
      screen.getByText(/Received a malformed event payload\./i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Status: Running/i)).toBeInTheDocument();
  });

  it("accepts exactly one terminal event and keeps later events visible", async () => {
    const { result } = renderHook(() =>
      useWorkbench("http://127.0.0.1:8000")
    );
    await waitFor(() =>
      expect(result.current.health?.tutorial_runtime).toBe("mock")
    );
    const threadId = result.current.threadId;
    openSocket();
    const deliver = (text: string) =>
      act(() => {
        FakeWebSocket.instances[0].onmessage?.({ data: text });
      });

    deliver(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 1, type: "task_started" })
      )
    );
    expect(result.current.status).toBe("running");
    deliver(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 2, type: "task_completed" })
      )
    );
    expect(result.current.status).toBe("success");
    expect(result.current.terminalEvent?.type).toBe("task_completed");
    // Flush the post-terminal artifact refresh so its state settles inside act.
    await act(async () => {});
    deliver(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 3, type: "task_failed" })
      )
    );
    expect(result.current.status).toBe("success");
    expect(result.current.terminalEvent?.type).toBe("task_completed");
    expect(result.current.events.map((entry) => entry.type)).toEqual([
      "task_started",
      "task_completed",
      "task_failed",
    ]);
  });

  it("failed and cancelled runs clear stale success artifacts and markdown", async () => {
    const { result } = renderHook(() =>
      useWorkbench("http://127.0.0.1:8000")
    );
    await waitFor(() =>
      expect(result.current.health?.tutorial_runtime).toBe("mock")
    );
    const threadId = result.current.threadId;
    stubFetch({
      "/api/upload": () =>
        jsonResponse({
          status: "uploaded",
          thread_id: threadId,
          files: [{ name: "constraints.md", size: 18 }],
        }),
      "/api/task": () =>
        jsonResponse({ status: "started", thread_id: threadId }, 202),
    });
    openSocket();
    const deliver = (text: string) =>
      act(() => {
        FakeWebSocket.instances[0].onmessage?.({ data: text });
      });

    act(() => {
      result.current.selectFile(constraintFile());
    });
    act(() => {
      result.current.upload();
    });
    await waitFor(() => expect(result.current.uploadedFile).not.toBeNull());
    act(() => {
      result.current.setQuery("Compare policies");
    });
    act(() => {
      result.current.submit();
    });
    await waitFor(() =>
      expect(
        vi.mocked(fetch).mock.calls.some(([input]) =>
          String(input).endsWith("/api/task")
        )
      ).toBe(true)
    );

    deliver(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 1, type: "task_started" })
      )
    );
    deliver(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 2, type: "task_completed" })
      )
    );
    expect(result.current.status).toBe("success");

    // A new run on the same thread clears the previous terminal display.
    // The start POST resolves asynchronously; await its promise chain
    // (`.finally` clearing taskStartPending) inside act so no update escapes.
    await act(async () => {
      result.current.submit();
    });
    expect(result.current.status).toBe("ready");
    expect(result.current.events).toEqual([]);
    expect(result.current.terminalEvent).toBeNull();

    deliver(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 1, type: "task_started" })
      )
    );
    deliver(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 2, type: "task_failed" })
      )
    );
    expect(result.current.status).toBe("failed");
    expect(result.current.terminalEvent?.type).toBe("task_failed");
    expect(result.current.files).toEqual([]);
    expect(result.current.markdown).toBeNull();

    // A cancelled run clears artifacts the same way.
    await act(async () => {
      result.current.submit();
    });
    deliver(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 1, type: "task_started" })
      )
    );
    deliver(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 2, type: "task_cancelled" })
      )
    );
    expect(result.current.status).toBe("cancelled");
    expect(result.current.terminalEvent?.type).toBe("task_cancelled");
    expect(result.current.files).toEqual([]);
    expect(result.current.markdown).toBeNull();
  });

  it("a WebSocket close before any terminal event sets connection-error with a stable message", async () => {
    await startAppRun();

    closeSocket(1001);

    expect(screen.getByText(/Status: Connection error/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Connection lost before the task finished\./i)
    ).toBeInTheDocument();
  });

  it("socket error before any terminal event sets connection-error with the exact stable message", async () => {
    await startAppRun();

    fireSocketError();

    expect(screen.getByText(/Status: Connection error/i)).toBeInTheDocument();
    expect(
      screen.getByText("Event stream connection failed.")
    ).toBeInTheDocument();
  });

  it("socket error after a terminal event preserves the terminal status", async () => {
    const threadId = await startAppRun();
    deliverMessage(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 2, type: "task_completed" })
      )
    );
    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();
    // Flush the post-terminal artifact refresh so its state settles inside act.
    await act(async () => {});

    fireSocketError();

    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();
    expect(
      screen.queryByText("Event stream connection failed.")
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Status: Connection error/i)
    ).not.toBeInTheDocument();
  });

  it("close 1013 shows the exact slow-consumer stream interruption message", async () => {
    await startAppRun();

    closeSocket(1013);

    expect(screen.getByText(/Status: Connection error/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /Event stream interrupted because the consumer was too slow\./i
      )
    ).toBeInTheDocument();
  });

  it("disconnect after a terminal event preserves the terminal status", async () => {
    const threadId = await startAppRun();
    deliverMessage(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 2, type: "task_completed" })
      )
    );
    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();
    // Flush the post-terminal artifact refresh so its state settles inside act.
    await act(async () => {});

    closeSocket(1001);

    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/Connection lost before the task finished\./i)
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Status: Connection error/i)
    ).not.toBeInTheDocument();
  });
});

describe("artifact listing, preview and downloads", () => {
  const MD_FILE = {
    name: "tutorial-report.md",
    path: "tutorial-report.md",
    size: 2048,
    media_type: "text/markdown",
  };
  const PDF_FILE = {
    name: "tutorial-report.pdf",
    path: "tutorial-report.pdf",
    size: 4096,
    media_type: "application/pdf",
  };

  function completeRun(threadId: string) {
    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 2,
          type: "task_completed",
          message: "Report done",
        })
      )
    );
  }

  function stubArtifactRoutes(
    threadId: string,
    files: unknown[],
    markdown = "# Report\n\nbody"
  ) {
    return stubFetch({
      [`/api/files?thread_id=${threadId}`]: () =>
        jsonResponse({ thread_id: threadId, files }),
      "&path=tutorial-report.md": () => new Response(markdown, { status: 200 }),
    });
  }

  it("calls GET /api/files with the same current UUID after task_completed and shows response-derived artifacts", async () => {
    const threadId = await startAppRun();
    const fetchMock = stubArtifactRoutes(threadId, [MD_FILE, PDF_FILE]);
    completeRun(threadId);

    expect(
      await screen.findByText(/tutorial-report\.md \(2048 bytes\)/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/tutorial-report\.pdf \(4096 bytes\)/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();

    const filesCall = fetchMock.mock.calls.find(([input]) =>
      String(input).includes("/api/files")
    );
    expect(String(filesCall?.[0])).toBe(
      `http://127.0.0.1:8000/api/files?thread_id=${threadId}`
    );
  });

  it("fetches Markdown through the server-returned relative path and renders it as plain text in a pre, never HTML", async () => {
    const threadId = await startAppRun();
    const markdown = "<script>alert('xss')</script>\n\n# Report\n\n**bold** text";
    stubArtifactRoutes(threadId, [MD_FILE], markdown);
    completeRun(threadId);

    const preview = await screen.findByText(/<script>alert\('xss'\)<\/script>/i);
    expect(preview.tagName).toBe("PRE");
    expect(preview.textContent).toBe(markdown);
    // The report content created no script or heading markup.
    expect(document.querySelector(".markdown-preview script")).toBeNull();
    expect(document.querySelector(".markdown-preview h1")).toBeNull();
    expect(
      screen.queryByRole("heading", { name: /^Report$/i })
    ).not.toBeInTheDocument();
  });

  it("renders Markdown and PDF download links with the current UUID and server-returned relative paths", async () => {
    const threadId = await startAppRun();
    stubArtifactRoutes(threadId, [MD_FILE, PDF_FILE]);
    completeRun(threadId);

    const mdLink = await screen.findByRole("link", {
      name: /download markdown/i,
    });
    expect(mdLink).toHaveAttribute(
      "href",
      `http://127.0.0.1:8000/api/download?thread_id=${threadId}&path=tutorial-report.md`
    );
    expect(mdLink).toHaveAttribute("download");

    const pdfLink = screen.getByRole("link", { name: /download pdf/i });
    expect(pdfLink).toHaveAttribute(
      "href",
      `http://127.0.0.1:8000/api/download?thread_id=${threadId}&path=tutorial-report.pdf`
    );
    expect(pdfLink).toHaveAttribute("download");
  });

  it("a failed Markdown preview fetch shows a stable preview-unavailable state and preserves success", async () => {
    const threadId = await startAppRun();
    stubFetch({
      [`/api/files?thread_id=${threadId}`]: () =>
        jsonResponse({ thread_id: threadId, files: [MD_FILE] }),
      "&path=tutorial-report.md": () => jsonResponse({ detail: "missing" }, 404),
    });
    completeRun(threadId);

    expect(await screen.findByText(/Preview unavailable\./i)).toBeInTheDocument();
    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();
    expect(document.querySelector(".markdown-preview")).toBeNull();
    expect(
      screen.getByRole("link", { name: /download markdown/i })
    ).toBeInTheDocument();
    // No raw status context is surfaced for the preview failure.
    expect(screen.queryByText(/HTTP 404/i)).not.toBeInTheDocument();
  });

  it("a file list without the Markdown report shows a stable empty state and keeps the PDF download", async () => {
    const threadId = await startAppRun();
    stubArtifactRoutes(threadId, [PDF_FILE]);
    completeRun(threadId);

    expect(
      await screen.findByText(/No Markdown report available\./i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();
    expect(document.querySelector(".markdown-preview")).toBeNull();
    expect(
      screen.getByRole("link", { name: /download pdf/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /download markdown/i })
    ).not.toBeInTheDocument();
  });

  it("a files fetch failure shows a stable preview-unavailable state without throwing", async () => {
    const threadId = await startAppRun();
    stubFetch({
      [`/api/files?thread_id=${threadId}`]: () =>
        jsonResponse({ detail: "missing" }, 500),
    });
    completeRun(threadId);

    expect(await screen.findByText(/Preview unavailable\./i)).toBeInTheDocument();
    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();
    expect(screen.getByText(/No artifacts yet/i)).toBeInTheDocument();
  });

  it("a new run clears the stale artifact list and Markdown preview before the next completion", async () => {
    const threadId = await startAppRun();
    stubArtifactRoutes(threadId, [MD_FILE, PDF_FILE]);
    completeRun(threadId);
    await screen.findByRole("link", { name: /download markdown/i });
    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /start research/i }));
    });

    expect(screen.getByText(/No artifacts yet/i)).toBeInTheDocument();
    expect(document.querySelector(".markdown-preview")).toBeNull();
    expect(
      screen.queryByRole("link", { name: /download markdown/i })
    ).not.toBeInTheDocument();
  });

  it("a new session clears the stale artifact list and Markdown preview", async () => {
    const threadId = await startAppRun();
    stubArtifactRoutes(threadId, [MD_FILE]);
    completeRun(threadId);
    await screen.findByRole("link", { name: /download markdown/i });

    fireEvent.click(screen.getByRole("button", { name: /new session/i }));

    expect(screen.getByText(/No artifacts yet/i)).toBeInTheDocument();
    expect(document.querySelector(".markdown-preview")).toBeNull();
    expect(
      screen.queryByRole("link", { name: /download markdown/i })
    ).not.toBeInTheDocument();
  });

  it("skips server-returned paths containing a separator and never builds a link or download from them", async () => {
    const threadId = await startAppRun();
    const fetchMock = stubFetch({
      [`/api/files?thread_id=${threadId}`]: () =>
        jsonResponse({
          thread_id: threadId,
          files: [{ ...MD_FILE, path: "output/report.md" }, PDF_FILE],
        }),
      "/api/download?": () => jsonResponse({ detail: "unexpected" }, 500),
    });
    completeRun(threadId);

    expect(
      await screen.findByText(/No Markdown report available\./i)
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /download pdf/i })).toHaveAttribute(
      "href",
      `http://127.0.0.1:8000/api/download?thread_id=${threadId}&path=tutorial-report.pdf`
    );
    expect(
      screen.queryByRole("link", { name: /download markdown/i })
    ).not.toBeInTheDocument();
    // Neither the download endpoint nor any anchor ever saw the invalid path.
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("output/report.md")
      )
    ).toBe(false);
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/api/download")
      )
    ).toBe(false);
  });

  it("refreshArtifacts keeps only safe current-thread files and fetches Markdown as plain text", async () => {
    const { result } = renderHook(() =>
      useWorkbench("http://127.0.0.1:8000")
    );
    await waitFor(() =>
      expect(result.current.health?.tutorial_runtime).toBe("mock")
    );
    const threadId = result.current.threadId;
    stubFetch({
      [`/api/files?thread_id=${threadId}`]: () =>
        jsonResponse({
          thread_id: threadId,
          files: [
            MD_FILE,
            PDF_FILE,
            {
              name: "evil.md",
              path: "../evil.md",
              size: 1,
              media_type: "text/markdown",
            },
          ],
        }),
      "&path=tutorial-report.md": () =>
        new Response("# Report\n\nbody", { status: 200 }),
    });

    act(() => {
      result.current.refreshArtifacts();
    });

    await waitFor(() => expect(result.current.files).toHaveLength(2));
    expect(result.current.markdown).toBe("# Report\n\nbody");
    expect(result.current.markdownError).toBeNull();
    expect(
      result.current.files.some((file) => file.path.includes("/"))
    ).toBe(false);
  });

  it("late artifact responses cannot populate a new session", async () => {
    const { result } = renderHook(() =>
      useWorkbench("http://127.0.0.1:8000")
    );
    await waitFor(() =>
      expect(result.current.health?.tutorial_runtime).toBe("mock")
    );
    const firstThreadId = result.current.threadId;
    openSocket();
    let resolveFiles: (response: Response) => void = () => undefined;
    const pending = new Promise<Response>((resolve) => {
      resolveFiles = resolve;
    });
    stubFetch({
      [`/api/files?thread_id=${firstThreadId}`]: () => pending,
      "/api/download?": () => new Response("late", { status: 200 }),
    });
    const deliver = (text: string) =>
      act(() => {
        FakeWebSocket.instances[0].onmessage?.({ data: text });
      });

    deliver(
      JSON.stringify(
        makeEvent({
          thread_id: firstThreadId,
          sequence: 1,
          type: "task_started",
        })
      )
    );
    deliver(
      JSON.stringify(
        makeEvent({
          thread_id: firstThreadId,
          sequence: 2,
          type: "task_completed",
        })
      )
    );
    expect(result.current.status).toBe("success");
    act(() => {
      result.current.newSession();
    });
    expect(result.current.threadId).not.toBe(firstThreadId);

    await act(async () => {
      resolveFiles(
        jsonResponse({ thread_id: firstThreadId, files: [MD_FILE, PDF_FILE] })
      );
    });

    expect(result.current.files).toEqual([]);
    expect(result.current.markdown).toBeNull();
    expect(result.current.markdownError).toBeNull();
  });
});

describe("contract", () => {
  function validEvent(overrides: Record<string, unknown> = {}) {
    return {
      version: 1,
      sequence: 3,
      thread_id: crypto.randomUUID(),
      type: "tool_started",
      message: "Calling mock internet_search",
      data: { provider: "mock" },
      timestamp: "2026-08-06T12:00:00Z",
      ...overrides,
    };
  }

  it("parseEvent accepts a valid TutorialEvent v1", () => {
    const event = validEvent();
    expect(parseEvent(JSON.stringify(event))).toEqual(event);
  });

  it("parseEvent rejects malformed JSON with a stable user-safe error", () => {
    const raw = `{"version": 1, "thread_id": "${crypto.randomUUID()}"} not-json`;
    let message = "";
    try {
      parseEvent(raw);
    } catch (error) {
      message = error instanceof Error ? error.message : String(error);
    }
    expect(message).toBe("Received a malformed event payload.");
    expect(message).not.toContain("not-json");
    expect(message).not.toContain(raw);
  });

  it("parseEvent rejects unknown event versions with a stable user-safe error", () => {
    const raw = JSON.stringify(
      validEvent({ version: 99, type: "task_started", data: {} })
    );
    let message = "";
    try {
      parseEvent(raw);
    } catch (error) {
      message = error instanceof Error ? error.message : String(error);
    }
    expect(message).toBe("Received an unsupported event version.");
    expect(message).not.toContain("99");
    expect(message).not.toContain(raw);
  });

  it("parseEvent rejects unknown event types", () => {
    const raw = JSON.stringify(
      validEvent({ type: "agent_skipped", data: {} })
    );
    expect(() => parseEvent(raw)).toThrow("Received an unsupported event payload.");
  });

  it("downloadUrl keeps the API base, current thread and relative artifact path", () => {
    const threadId = crypto.randomUUID();
    expect(downloadUrl("http://127.0.0.1:8000/", threadId, "tutorial-report.md")).toBe(
      `http://127.0.0.1:8000/api/download?thread_id=${threadId}&path=tutorial-report.md`
    );
  });

  it("downloadUrl never accepts filesystem paths", () => {
    const threadId = crypto.randomUUID();
    expect(() => downloadUrl("http://127.0.0.1:8000", threadId, "/etc/passwd")).toThrow();
    expect(() => downloadUrl("http://127.0.0.1:8000", threadId, "../secret.md")).toThrow();
    expect(() => downloadUrl("http://127.0.0.1:8000", threadId, "output/report.md")).toThrow();
    expect(() => downloadUrl("http://127.0.0.1:8000", threadId, "")).toThrow();
  });

  it("requestJson surfaces only stable HTTP status and detail context", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "file too large" }), { status: 413 })
      )
    );
    await expect(
      requestJson("http://127.0.0.1:8000", "/api/upload", { method: "POST" })
    ).rejects.toThrow("HTTP 413: file too large");
    vi.unstubAllGlobals();
  });

  it("requestJson never leaks raw response text", async () => {
    const rawBody = "<html>secret-token-abc123</html>";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(rawBody, { status: 500 }))
    );
    let message = "";
    try {
      await requestJson("http://127.0.0.1:8000", "/health");
    } catch (error) {
      message = error instanceof Error ? error.message : String(error);
    }
    expect(message).toBe("HTTP 500");
    expect(message).not.toContain("secret-token-abc123");
    expect(message).not.toContain(rawBody);
    vi.unstubAllGlobals();
  });

  it("requestJson resolves the JSON body exactly once on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ok" }), { status: 200 })
      )
    );
    await expect(
      requestJson("http://127.0.0.1:8000", "/health")
    ).resolves.toEqual({ status: "ok" });
    vi.unstubAllGlobals();
  });

  it("parseEvent accepts citation_started and citation_completed as v1 events", () => {
    const started = validEvent({ type: "citation_started", data: {} });
    expect(parseEvent(JSON.stringify(started))).toEqual(started);
    const completed = validEvent({
      type: "citation_completed",
      data: {
        status: "completed",
        partition_count: 3,
        report_fingerprint: "a".repeat(64),
        limitations: [],
      },
    });
    expect(parseEvent(JSON.stringify(completed))).toEqual(completed);
  });

  it("parseEvent still rejects unknown types and versions after adding citation events", () => {
    expect(() =>
      parseEvent(JSON.stringify(validEvent({ type: "citation_skipped" })))
    ).toThrow("Received an unsupported event payload.");
    expect(() =>
      parseEvent(JSON.stringify(validEvent({ type: "citation_completed", version: 99 })))
    ).toThrow("Received an unsupported event version.");
  });

  it("parseCitationsReport accepts null or missing metrics and rejects malformed metrics", () => {
    const base = {
      schema_version: "1.0.0",
      report_fingerprint: "a".repeat(64),
      provenance: { dataset_id: "seed-10-v1", corpus_id: "agent-research-corpus-v1" },
    };
    const partition = {
      partition_id: "rule/offline",
      support: "mixed",
      claims: [],
      limitations: [],
    };
    expect(
      parseCitationsReport({
        ...base,
        partitions: { "rule/offline": { ...partition, metrics: null } },
      })
    ).not.toBeNull();
    expect(
      parseCitationsReport({
        ...base,
        partitions: { "rule/offline": { ...partition } },
      })
    ).not.toBeNull();
    expect(
      parseCitationsReport({
        ...base,
        partitions: { "rule/offline": { ...partition, metrics: "garbage" } },
      })
    ).toBeNull();
  });

  it("getCitations requests the exact citations URL and validates the report", async () => {
    const threadId = crypto.randomUUID();
    const report = {
      schema_version: "1.0.0",
      report_fingerprint: "a".repeat(64),
      provenance: { dataset_id: "seed-10-v1", corpus_id: "agent-research-corpus-v1" },
      partitions: {
        "rule/offline": {
          partition_id: "rule/offline",
          support: "mixed",
          metrics: null,
          claims: [],
          limitations: [],
        },
      },
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ thread_id: threadId, report }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(getCitations("http://127.0.0.1:8000/", threadId)).resolves.toMatchObject({
      thread_id: threadId,
    });
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      `http://127.0.0.1:8000/api/citations?thread_id=${threadId}`
    );
    vi.unstubAllGlobals();
  });

  it("requestJson rejects network failures with a stable message", async () => {
    const raw = "secret-host /Users/private/token";
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error(raw)));
    let message = "";
    try {
      await requestJson("http://127.0.0.1:8000", "/health");
    } catch (error) {
      message = error instanceof Error ? error.message : String(error);
    }
    expect(message).toBe("Network request failed.");
    expect(message).not.toContain(raw);
    vi.unstubAllGlobals();
  });
});

describe("citation events, report and panel", () => {
  const CITATION_REPORT_FILE = {
    name: "citation-report.json",
    path: "citation-report.json",
    size: 512,
    media_type: "application/json",
  };
  const CITATION_PARTITIONS_FILE = {
    name: "citation-partitions.jsonl",
    path: "citation-partitions.jsonl",
    size: 128,
    media_type: "application/octet-stream",
  };

  function citationReport(overrides: Record<string, unknown> = {}) {
    return {
      schema_version: "1.0.0",
      report_fingerprint: "c".repeat(64),
      provenance: {
        dataset_id: "seed-10-v1",
        corpus_id: "agent-research-corpus-v1",
      },
      partitions: {
        "rule/offline": {
          partition_id: "rule/offline",
          support: "mixed",
          metrics: { precision: 0.9, recall: 0.75 },
          claims: [],
          limitations: [],
        },
      },
      ...overrides,
    };
  }

  function citationCompletedData(overrides: Record<string, unknown> = {}) {
    return {
      status: "completed",
      partition_count: 3,
      report_fingerprint: "b".repeat(64),
      limitations: [],
      ...overrides,
    };
  }

  function stubCitationRoutes(threadId: string, report: unknown) {
    return stubFetch({
      [`/api/citations?thread_id=${threadId}`]: () =>
        jsonResponse({ thread_id: threadId, report }),
      [`/api/files?thread_id=${threadId}`]: () =>
        jsonResponse({
          thread_id: threadId,
          files: [CITATION_REPORT_FILE, CITATION_PARTITIONS_FILE],
        }),
    });
  }

  function deliverCitationRun(
    threadId: string,
    data: Record<string, unknown> = citationCompletedData()
  ) {
    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 2,
          type: "citation_started",
          message: "Evaluating citations",
        })
      )
    );
    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 3,
          type: "citation_completed",
          message: "Citations evaluated",
          data,
        })
      )
    );
  }

  it("accepts citation_started and citation_completed in the v1 stream in order without altering run status", async () => {
    const threadId = await startAppRun();
    stubCitationRoutes(threadId, citationReport());
    deliverCitationRun(threadId);

    // Citation events are non-terminal: the run stays running.
    expect(screen.getByText(/Status: Running/i)).toBeInTheDocument();
    expect(screen.getByText("citation_started")).toBeInTheDocument();
    expect(screen.getByText("citation_completed")).toBeInTheDocument();

    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 4,
          type: "task_completed",
          message: "Report done",
        })
      )
    );
    expect(screen.getByText(/Status: Success/i)).toBeInTheDocument();

    // The complete chronological timeline is preserved in ascending order.
    const sequences = screen
      .getAllByText(/^#\d+$/)
      .map((node) => node.textContent);
    expect(sequences).toEqual(["#1", "#2", "#3", "#4"]);
    await act(async () => {});
  });

  it("calls GET /api/citations with the current UUID after a completed citation evaluation", async () => {
    const threadId = await startAppRun();
    const fetchMock = stubCitationRoutes(threadId, citationReport());
    deliverCitationRun(threadId);

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).includes("/api/citations")
        )
      ).toBe(true)
    );
    const citationsCall = fetchMock.mock.calls.find(([input]) =>
      String(input).includes("/api/citations")
    );
    expect(String(citationsCall?.[0])).toBe(
      `http://127.0.0.1:8000/api/citations?thread_id=${threadId}`
    );
    await act(async () => {});
  });

  it("renders claims, distinct support states and evidence snippets with sources as text", async () => {
    const threadId = await startAppRun();
    stubCitationRoutes(
      threadId,
      citationReport({
        partitions: {
          "rule/offline": {
            partition_id: "rule/offline",
            support: "mixed",
            metrics: { precision: 0.9 },
            claims: [
              {
                claim: "Agents orchestrate tools",
                support: "supported",
                evidence: [
                  { snippet: "doc line one", source: "seed-doc-01.txt" },
                ],
              },
              {
                claim: "A claim with no backing evidence",
                support: "unsupported",
                evidence: [],
              },
              {
                claim: "An unverifiable claim",
                support: "unknown",
                evidence: [{ snippet: "unclear text", source: "seed-doc-02.txt" }],
              },
              {
                claim: "A claim skipped by evaluation",
                support: "skipped",
                evidence: [],
              },
            ],
            limitations: [],
          },
        },
      })
    );
    deliverCitationRun(threadId);

    const panel = await screen.findByRole("region", { name: /citations/i });
    // The four support states stay distinct — none is merged into another.
    expect(within(panel).getByText(/Support: supported/i)).toBeInTheDocument();
    expect(within(panel).getByText(/Support: unsupported/i)).toBeInTheDocument();
    expect(within(panel).getByText(/Support: unknown/i)).toBeInTheDocument();
    expect(within(panel).getByText(/Support: skipped/i)).toBeInTheDocument();
    expect(within(panel).getByText(/Agents orchestrate tools/i)).toBeInTheDocument();
    expect(within(panel).getByText(/A claim with no backing evidence/i)).toBeInTheDocument();
    // Evidence snippets and their sources render as plain text.
    expect(within(panel).getByText(/doc line one/i)).toBeInTheDocument();
    expect(within(panel).getByText(/Source: seed-doc-01\.txt/i)).toBeInTheDocument();
    expect(within(panel).getByText(/Source: seed-doc-02\.txt/i)).toBeInTheDocument();
    // The snippet text created no script or element markup.
    expect(document.querySelector(".citation-panel script")).toBeNull();
    await act(async () => {});
  });

  it("renders null metrics as a distinct no-metrics state without crashing", async () => {
    const threadId = await startAppRun();
    stubCitationRoutes(
      threadId,
      citationReport({
        partitions: {
          "rule/offline": {
            partition_id: "rule/offline",
            support: "mixed",
            metrics: null,
            claims: [
              {
                claim: "Claim with null metrics",
                support: "supported",
                evidence: [],
              },
            ],
            limitations: [],
          },
        },
      })
    );
    deliverCitationRun(threadId);

    const panel = await screen.findByRole("region", { name: /citations/i });
    expect(within(panel).getByText(/No metrics\./i)).toBeInTheDocument();
    expect(within(panel).getByText(/Claim with null metrics/i)).toBeInTheDocument();
    await act(async () => {});
  });

  it("shows limitations from citation_completed and links citation artifacts via server-returned relative paths", async () => {
    const threadId = await startAppRun();
    stubCitationRoutes(threadId, citationReport());
    deliverCitationRun(threadId, {
      status: "completed",
      partition_count: 3,
      report_fingerprint: "b".repeat(64),
      limitations: ["LLM judgment may be wrong", "Corpus limited to seed-10"],
    });

    const panel = await screen.findByRole("region", { name: /citations/i });
    expect(within(panel).getByText(/LLM judgment may be wrong/i)).toBeInTheDocument();
    expect(within(panel).getByText(/Corpus limited to seed-10/i)).toBeInTheDocument();
    expect(within(panel).getByText(/Evaluation: completed/i)).toBeInTheDocument();

    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 4,
          type: "task_completed",
          message: "Report done",
        })
      )
    );
    const reportLink = await screen.findByRole("link", {
      name: /download citation report/i,
    });
    expect(reportLink).toHaveAttribute(
      "href",
      `http://127.0.0.1:8000/api/download?thread_id=${threadId}&path=citation-report.json`
    );
    expect(reportLink).toHaveAttribute("download");
    const partitionsLink = screen.getByRole("link", {
      name: /download citation partitions/i,
    });
    expect(partitionsLink).toHaveAttribute(
      "href",
      `http://127.0.0.1:8000/api/download?thread_id=${threadId}&path=citation-partitions.jsonl`
    );
    await act(async () => {});
  });

  it("a failed citation evaluation shows failed status and limitations and never fetches the report", async () => {
    const threadId = await startAppRun();
    const fetchMock = stubCitationRoutes(threadId, citationReport());
    deliverCitationRun(threadId, {
      status: "failed",
      partition_count: 0,
      report_fingerprint: "b".repeat(64),
      limitations: ["Citation engine unavailable"],
    });

    const panel = await screen.findByRole("region", { name: /citations/i });
    expect(within(panel).getByText(/Evaluation: failed/i)).toBeInTheDocument();
    expect(
      within(panel).getByText(/Citation engine unavailable/i)
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/api/citations")
      )
    ).toBe(false);
    await act(async () => {});
  });

  it("rejects a citation report with malformed metrics and shows a stable unavailable message", async () => {
    const threadId = await startAppRun();
    stubFetch({
      [`/api/citations?thread_id=${threadId}`]: () =>
        jsonResponse({
          thread_id: threadId,
          report: citationReport({
            partitions: {
              "rule/offline": {
                partition_id: "rule/offline",
                support: "mixed",
                metrics: "not-an-object",
                claims: [],
                limitations: [],
              },
            },
          }),
        }),
    });
    deliverCitationRun(threadId);

    expect(
      await screen.findByText(/Citation results are unavailable\./i)
    ).toBeInTheDocument();
    // The report body is never rendered.
    expect(screen.queryByText(/rule\/offline/i)).toBeNull();
    await act(async () => {});
  });

  it("ignores citation events for a foreign thread and never fetches citations for it", async () => {
    const threadId = await startAppRun();
    const fetchMock = stubCitationRoutes(threadId, citationReport());
    const foreignId = crypto.randomUUID();

    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: foreignId,
          sequence: 2,
          type: "citation_completed",
          message: "foreign citations",
          data: citationCompletedData(),
        })
      )
    );

    expect(screen.getByText(/No citation results yet\./i)).toBeInTheDocument();
    expect(screen.queryByText(/foreign citations/i)).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/api/citations")
      )
    ).toBe(false);
    await act(async () => {});
  });

  it("never builds citation links from unsafe server-returned paths", async () => {
    const threadId = await startAppRun();
    const fetchMock = stubFetch({
      [`/api/citations?thread_id=${threadId}`]: () =>
        jsonResponse({ thread_id: threadId, report: citationReport() }),
      [`/api/files?thread_id=${threadId}`]: () =>
        jsonResponse({
          thread_id: threadId,
          files: [
            { ...CITATION_REPORT_FILE, path: "output/citation-report.json" },
            CITATION_PARTITIONS_FILE,
          ],
        }),
      "&path=": () => jsonResponse({ detail: "unexpected" }, 500),
    });
    deliverCitationRun(threadId);
    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 4,
          type: "task_completed",
          message: "Report done",
        })
      )
    );

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) => String(input).includes("/api/files"))
      ).toBe(true)
    );
    // The unsafe report path never becomes a link or a download request.
    expect(
      screen.queryByRole("link", { name: /download citation report/i })
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /download citation partitions/i })
    ).toHaveAttribute(
      "href",
      `http://127.0.0.1:8000/api/download?thread_id=${threadId}&path=citation-partitions.jsonl`
    );
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("output/citation-report.json")
      )
    ).toBe(false);
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/api/download")
      )
    ).toBe(false);
    await act(async () => {});
  });

  it("newSession clears citation summary, report and error state", async () => {
    const { result } = renderHook(() =>
      useWorkbench("http://127.0.0.1:8000")
    );
    await waitFor(() =>
      expect(result.current.health?.tutorial_runtime).toBe("mock")
    );
    const threadId = result.current.threadId;
    stubFetch({
      [`/api/citations?thread_id=${threadId}`]: () =>
        jsonResponse({ thread_id: threadId, report: citationReport() }),
    });
    openSocket();
    const deliver = (text: string) =>
      act(() => {
        FakeWebSocket.instances[0].onmessage?.({ data: text });
      });

    deliver(
      JSON.stringify(
        makeEvent({ thread_id: threadId, sequence: 1, type: "citation_completed", data: citationCompletedData() })
      )
    );
    await waitFor(() => expect(result.current.citations).not.toBeNull());
    expect(result.current.citationSummary?.status).toBe("completed");

    act(() => {
      result.current.newSession();
    });
    expect(result.current.citations).toBeNull();
    expect(result.current.citationSummary).toBeNull();
    expect(result.current.citationsError).toBeNull();
    expect(result.current.citationsLoading).toBe(false);
  });

  it("renders the responsive class hooks the narrow/wide layout rules target", async () => {
    const threadId = await startAppRun();
    stubCitationRoutes(
      threadId,
      citationReport({
        partitions: {
          "rule/offline": {
            partition_id: "rule/offline",
            support: "mixed",
            metrics: { precision: 0.9 },
            claims: [
              {
                claim: "Agents orchestrate tools",
                support: "supported",
                evidence: [],
              },
            ],
            limitations: [],
          },
        },
      })
    );
    deliverCitationRun(threadId);
    deliverMessage(
      JSON.stringify(
        makeEvent({
          thread_id: threadId,
          sequence: 4,
          type: "task_completed",
          message: "Report done",
        })
      )
    );

    // The panel DOM exposes the class hooks the responsive stylesheet
    // selects on (min-width 720px grid, max-width 640px compact layout):
    // panel section, partition list, partition card, downloads and links.
    const panel = await screen.findByRole("region", { name: /citations/i });
    expect(panel).toHaveClass("citation-panel");
    expect(panel.querySelector(".citation-partitions")).not.toBeNull();
    expect(panel.querySelector(".citation-partition")).not.toBeNull();
    expect(panel.querySelector(".citation-downloads")).not.toBeNull();
    expect(
      panel.querySelector(".citation-downloads .download")
    ).not.toBeNull();
    await act(async () => {});
  });
});
