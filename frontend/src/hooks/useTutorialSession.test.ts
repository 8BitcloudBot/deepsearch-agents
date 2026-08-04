import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import {
  HEARTBEAT_INTERVAL_MS,
  useTutorialSession,
} from "./useTutorialSession";
import type { TutorialEvent } from "../types";

const BASE = "http://127.0.0.1:8000";

/** Minimal controllable WebSocket double for jsdom tests. */
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  url: string;
  readyState = 0; // CONNECTING
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

  // Test helpers
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

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

function okJson(body: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

describe("useTutorialSession", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    FakeWebSocket.instances = [];
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("WebSocket", FakeWebSocket);
    // shouldAdvanceTime keeps @testing-library waitFor polling under fake
    // timers (vitest's sinon timers are not auto-detected by waitFor).
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("mints a fresh UUID thread id", () => {
    const { result } = renderHook(() => useTutorialSession(BASE));
    expect(result.current.threadId).toMatch(UUID_RE);
  });

  it("opens the WebSocket at the thread URL before POSTing the task", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));

    let runPromise: Promise<void>;
    act(() => {
      runPromise = result.current.run("research aspirin");
    });

    const ws = FakeWebSocket.instances[0];
    expect(ws).toBeDefined();
    expect(ws.url).toBe(`ws://127.0.0.1:8000/ws/${result.current.threadId}`);

    // No POST before the open handshake completes.
    expect(fetchMock).not.toHaveBeenCalled();

    await act(async () => {
      ws.open();
      await runPromise;
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [input, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(String(input)).toBe(`${BASE}/api/task`);
    expect(JSON.parse(String(init.body))).toEqual({
      query: "research aspirin",
      thread_id: result.current.threadId,
    });
    expect(result.current.status).toBe("running");
  });

  it("sends a ping heartbeat every 25 seconds while the socket is open", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      throw new Error(`unexpected fetch: ${String(input)}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));

    act(() => {
      void result.current.run("q");
    });
    const ws = FakeWebSocket.instances[0];
    await act(async () => {
      ws.open();
    });

    act(() => {
      vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS);
    });
    expect(ws.sent).toEqual([JSON.stringify({ type: "ping" })]);

    act(() => {
      vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS);
    });
    expect(ws.sent).toEqual([
      JSON.stringify({ type: "ping" }),
      JSON.stringify({ type: "ping" }),
    ]);
  });

  it("keeps heartbeat pong messages out of the event feed", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      throw new Error(`unexpected fetch: ${String(input)}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));
    act(() => {
      void result.current.run("q");
    });
    const ws = FakeWebSocket.instances[0];
    await act(async () => {
      ws.open();
    });

    act(() => ws.receive({ type: "pong" }));
    expect(result.current.events).toHaveLength(0);

    const valid = makeEvent("tool_started", {
      data: { tool_name: "internet_search" },
    });
    act(() => ws.receive(valid));
    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0].type).toBe("tool_started");
  });

  it("rejects schema-invalid frames and keeps them out of the feed", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      throw new Error(`unexpected fetch: ${String(input)}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));
    act(() => {
      void result.current.run("q");
    });
    const ws = FakeWebSocket.instances[0];
    await act(async () => {
      ws.open();
    });

    // Missing required fields.
    act(() => ws.receive({ type: "task_started", message: "start" }));
    // Unknown event type.
    act(() =>
      ws.receive({ ...makeEvent("task_started"), type: "totally_bogus" })
    );
    // data must be a JSON object, not a bare string.
    act(() =>
      ws.receive({ ...makeEvent("task_started"), data: "not-an-object" })
    );
    // sequence must be a positive integer.
    act(() => ws.receive({ ...makeEvent("task_started"), sequence: 0 }));
    // data must be a plain JSON object, not an array. (A function-valued
    // field is dropped by JSON.stringify in the test double, so the original
    // frame serialized into a valid event; an array survives serialization.)
    act(() => ws.receive({ ...makeEvent("task_started"), data: [1, 2] }));

    expect(result.current.events).toHaveLength(0);
  });

  it("refreshes artifacts after a terminal event", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      if (url.includes("/api/files")) {
        return okJson({
          thread_id: "t",
          files: [
            { name: "tutorial-report.md", path: "tutorial-report.md", size: 10, media_type: "text/markdown" },
            { name: "tutorial-report.pdf", path: "tutorial-report.pdf", size: 20, media_type: "application/pdf" },
          ],
        });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));
    act(() => {
      void result.current.run("q");
    });
    const ws = FakeWebSocket.instances[0];
    act(() => ws.open());

    act(() =>
      ws.receive(
        makeEvent("task_completed", {
          thread_id: result.current.threadId,
          message: "",
        })
      )
    );

    await waitFor(() => {
      expect(result.current.status).toBe("completed");
    });
    await waitFor(() => {
      expect(result.current.artifacts.map((a) => a.name)).toEqual([
        "tutorial-report.md",
        "tutorial-report.pdf",
      ]);
    });
    const fileCalls = fetchMock.mock.calls.filter((c) =>
      String(c[0]).includes("/api/files")
    );
    expect(fileCalls.length).toBeGreaterThan(0);
  });

  it("maps terminal event types to status", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      if (String(input).includes("/api/files")) {
        return okJson({ thread_id: "t", files: [] });
      }
      throw new Error(`unexpected fetch: ${String(input)}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));
    act(() => {
      void result.current.run("q");
    });
    const ws = FakeWebSocket.instances[0];
    act(() => ws.open());

    act(() =>
      ws.receive(makeEvent("task_failed", { thread_id: result.current.threadId }))
    );
    await waitFor(() => expect(result.current.status).toBe("failed"));
  });

  it("posts cancel to the cancel endpoint", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      if (url.includes("/cancel")) {
        return okJson({ thread_id: "t", status: "cancelled" });
      }
      if (url.includes("/api/files")) {
        return okJson({ thread_id: "t", files: [] });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));
    act(() => {
      void result.current.run("q");
    });
    const ws = FakeWebSocket.instances[0];
    act(() => ws.open());

    await act(async () => {
      await result.current.cancel();
    });

    const cancelCall = fetchMock.mock.calls.find((c) =>
      String(c[0]).includes("/cancel")
    );
    expect(cancelCall).toBeDefined();
    expect(String(cancelCall![0])).toBe(
      `${BASE}/api/task/${result.current.threadId}/cancel`
    );
  });

  it("uploads constraints for the same thread before the task starts", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/upload")) {
        return okJson({
          status: "uploaded",
          thread_id: "t",
          files: [{ name: "constraints.md", size: 7 }],
        });
      }
      if (url.endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));

    const file = new File(["# rules"], "constraints.md", {
      type: "text/markdown",
    });
    await act(async () => {
      await result.current.upload([file]);
    });

    expect(result.current.uploadedFiles).toEqual([
      { name: "constraints.md", size: 7 },
    ]);
    const uploadCall = fetchMock.mock.calls.find((c) =>
      String(c[0]).endsWith("/api/upload")
    );
    expect(uploadCall).toBeDefined();
    const body = uploadCall![1]!.body as FormData;
    expect(body.get("thread_id")).toBe(result.current.threadId);
    expect(body.get("files")).toBe(file);

    act(() => {
      void result.current.run("q");
    });
    const ws = FakeWebSocket.instances[0];
    act(() => ws.open());

    await waitFor(() => {
      const taskCall = fetchMock.mock.calls.find((c) =>
        String(c[0]).endsWith("/api/task")
      );
      const sent = JSON.parse(String(taskCall![1]!.body)) as {
        thread_id: string;
      };
      expect(sent.thread_id).toBe(result.current.threadId);
    });
  });

  it("surfaces start failures as an error status", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/task")) {
        return { ok: false, status: 409, text: async () => "duplicate" } as Response;
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));

    let runPromise: Promise<void>;
    act(() => {
      runPromise = result.current.run("q");
    });
    const ws = FakeWebSocket.instances[0];
    await act(async () => {
      ws.open();
      await runPromise;
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toContain("409");
  });

  it("allows a second run after the first completes", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      if (url.includes("/api/files")) {
        return okJson({ thread_id: "t", files: [] });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));

    // First run reaches a terminal event, which releases the socket.
    act(() => {
      void result.current.run("first");
    });
    let ws = FakeWebSocket.instances[0];
    act(() => ws.open());
    act(() =>
      ws.receive(
        makeEvent("task_completed", { thread_id: result.current.threadId })
      )
    );
    await waitFor(() => expect(result.current.status).toBe("completed"));
    expect(ws.closed).toBe(true);

    // Second run opens a fresh socket and POSTs again.
    act(() => {
      void result.current.run("second");
    });
    ws = FakeWebSocket.instances[1];
    expect(ws).toBeDefined();
    expect(ws.url).toBe(`ws://127.0.0.1:8000/ws/${result.current.threadId}`);
    act(() => ws.open());
    await waitFor(() => {
      const taskCalls = fetchMock.mock.calls.filter((c) =>
        String(c[0]).endsWith("/api/task")
      );
      expect(taskCalls).toHaveLength(2);
      expect(JSON.parse(String(taskCalls[1]![1]!.body))).toMatchObject({
        query: "second",
      });
    });
    expect(result.current.status).toBe("running");
  });

  it("releases the socket when the task POST fails so a retry can run", async () => {
    let fail = true;
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/task")) {
        if (fail) {
          return { ok: false, status: 500, text: async () => "boom" } as Response;
        }
        return okJson({ status: "started", thread_id: "t" });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));

    let runPromise: Promise<void>;
    act(() => {
      runPromise = result.current.run("first");
    });
    const ws0 = FakeWebSocket.instances[0];
    await act(async () => {
      ws0.open();
      await runPromise;
    });

    expect(result.current.status).toBe("error");
    // The failed POST must not leave a dangling socket behind.
    expect(ws0.closed).toBe(true);

    // A retry opens a fresh socket and can POST again.
    fail = false;
    act(() => {
      runPromise = result.current.run("second");
    });
    const ws1 = FakeWebSocket.instances[1];
    expect(ws1).toBeDefined();
    expect(ws1).not.toBe(ws0);
    await act(async () => {
      ws1.open();
      await runPromise;
    });
    const taskCalls = fetchMock.mock.calls.filter((c) =>
      String(c[0]).endsWith("/api/task")
    );
    expect(taskCalls).toHaveLength(2);
    expect(JSON.parse(String(taskCalls[1]![1]!.body))).toMatchObject({
      query: "second",
    });
    expect(result.current.status).toBe("running");
  });

  it("does not flip to running when the socket closes mid-POST", async () => {
    let resolvePost: ((res: Response) => void) | undefined;
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/task")) {
        return new Promise<Response>((r) => {
          resolvePost = r;
        });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));

    let runPromise: Promise<void>;
    act(() => {
      runPromise = result.current.run("q");
    });
    const ws = FakeWebSocket.instances[0];
    act(() => ws.open());

    // The socket dies while the POST is still in flight.
    act(() => ws.close());
    await act(async () => {
      resolvePost?.(okJson({ status: "started", thread_id: "t" }));
      await runPromise;
    });

    expect(result.current.status).toBe("error");
  });

  it("allows a second run after a task_failed terminal event", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      if (url.includes("/api/files")) {
        return okJson({ thread_id: "t", files: [] });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));

    // First run ends in a provider failure terminal event.
    act(() => {
      void result.current.run("first");
    });
    let ws = FakeWebSocket.instances[0];
    act(() => ws.open());
    act(() =>
      ws.receive(
        makeEvent("task_failed", { thread_id: result.current.threadId })
      )
    );
    await waitFor(() => expect(result.current.status).toBe("failed"));
    expect(ws.closed).toBe(true);

    // The failed run releases the socket, so Run can start a fresh task.
    act(() => {
      void result.current.run("second");
    });
    ws = FakeWebSocket.instances[1];
    expect(ws).toBeDefined();
    expect(ws.url).toBe(`ws://127.0.0.1:8000/ws/${result.current.threadId}`);
    act(() => ws.open());
    await waitFor(() => {
      const taskCalls = fetchMock.mock.calls.filter((c) =>
        String(c[0]).endsWith("/api/task")
      );
      expect(taskCalls).toHaveLength(2);
      expect(JSON.parse(String(taskCalls[1]![1]!.body))).toMatchObject({
        query: "second",
      });
    });
    expect(result.current.status).toBe("running");
  });

  it("allows a second run after cancel", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      if (url.includes("/cancel")) {
        return okJson({ thread_id: "t", status: "cancelled" });
      }
      if (url.includes("/api/files")) {
        return okJson({ thread_id: "t", files: [] });
      }
      throw new Error(`unexpected fetch: ${url}`);
    });
    const { result } = renderHook(() => useTutorialSession(BASE));

    act(() => {
      void result.current.run("first");
    });
    const ws0 = FakeWebSocket.instances[0];
    act(() => ws0.open());

    await act(async () => {
      await result.current.cancel();
    });
    expect(result.current.status).toBe("cancelled");
    expect(ws0.closed).toBe(true);

    // After cancel the workbench can run again on a fresh socket.
    act(() => {
      void result.current.run("second");
    });
    const ws1 = FakeWebSocket.instances[1];
    expect(ws1).toBeDefined();
    expect(ws1).not.toBe(ws0);
    act(() => ws1.open());
    await waitFor(() => {
      const taskCalls = fetchMock.mock.calls.filter((c) =>
        String(c[0]).endsWith("/api/task")
      );
      expect(taskCalls).toHaveLength(2);
      expect(JSON.parse(String(taskCalls[1]![1]!.body))).toMatchObject({
        query: "second",
      });
    });
    expect(result.current.status).toBe("running");
  });

  it("clears the heartbeat and closes the socket on unmount", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/task")) {
        return okJson({ status: "started", thread_id: "t" });
      }
      throw new Error(`unexpected fetch: ${String(input)}`);
    });
    const { result, unmount } = renderHook(() => useTutorialSession(BASE));
    act(() => {
      void result.current.run("q");
    });
    const ws = FakeWebSocket.instances[0];
    act(() => ws.open());

    const sentBefore = ws.sent.length;
    unmount();

    act(() => {
      vi.advanceTimersByTime(HEARTBEAT_INTERVAL_MS * 3);
    });
    expect(ws.closed).toBe(true);
    expect(ws.sent.length).toBe(sentBefore);
  });
});
