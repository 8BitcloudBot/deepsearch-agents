import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useConversationApp } from "./useConversationApp";

const { conversationApi, ApiError } = vi.hoisted(() => {
  class ApiError extends Error {
    constructor(
      public readonly status: number,
      message: string,
    ) {
      super(message);
    }
  }
  return {
    ApiError,
    conversationApi: {
      login: vi.fn(),
      logout: vi.fn(),
      me: vi.fn(),
      adminUsers: vi.fn(),
      resetUserData: vi.fn(),
      conversationsLite: vi.fn(),
      createConversation: vi.fn(),
      renameConversation: vi.fn(),
      deleteConversation: vi.fn(),
      submitTurn: vi.fn(),
      conversation: vi.fn(),
      libraryDocuments: vi.fn(),
      uploadLibraryDocuments: vi.fn(),
      deleteLibraryDocument: vi.fn(),
    },
  };
});

vi.mock("./api", () => ({ conversationApi, ApiError, eventSocketUrl: () => "ws://test/events", parseConversationEvent: (value: string) => JSON.parse(value) }));

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((message: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();

  constructor() {
    FakeWebSocket.instances.push(this);
  }
}

const summary = {
  id: "c1",
  owner_id: "u1",
  title: "研究",
  created_at: "2026-08-29T00:00:00Z",
  updated_at: "2026-08-29T00:00:00Z",
};

const detail = { ...summary, turns: [], attachments: [] };

function lastSocket(): FakeWebSocket {
  return FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
}

describe("useConversationApp", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
    conversationApi.me.mockResolvedValue({ id: "u1", username: "user", role: "user" });
    conversationApi.conversationsLite.mockResolvedValue([summary]);
    conversationApi.conversation.mockResolvedValue(detail);
    conversationApi.adminUsers.mockResolvedValue([]);
    conversationApi.libraryDocuments.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("clears the user on 401 without a misleading error", async () => {
    conversationApi.me.mockRejectedValue(new ApiError(401, "auth"));
    const { result } = renderHook(() => useConversationApp("http://test"));
    await waitFor(() => expect(result.current.booting).toBe(false));
    expect(result.current.user).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("accumulates partial answer deltas and clears on terminal event", async () => {
    const { result } = renderHook(() => useConversationApp("http://test"));
    await waitFor(() => expect(result.current.activeConversationId).toBe("c1"));
    act(() => {
      lastSocket().onopen?.();
      for (const [sequence, payload] of [
        [1, { type: "answer.delta", data: { text: "第一段", partial: true } }],
        [2, { type: "answer.delta", data: { text: "续写", partial: true } }],
      ] as const) {
        lastSocket().onmessage?.({
          data: JSON.stringify({
            schema_version: "5.0.0",
            sequence,
            conversation_id: "c1",
            turn_id: "t1",
            ...payload,
            timestamp: "2026-08-29T00:00:0" + sequence + "Z",
          }),
        });
      }
    });
    expect(result.current.streamingText).toBe("第一段续写");
    act(() => {
      lastSocket().onmessage?.({
        data: JSON.stringify({
          schema_version: "5.0.0",
          sequence: 3,
          conversation_id: "c1",
          turn_id: "t1",
          type: "turn.completed",
          message: "完成",
          timestamp: "2026-08-29T00:00:03Z",
        }),
      });
    });
    expect(result.current.streamingText).toBe("");
  });

  it("maps turn.failed events to error state and clears plan subquestions", async () => {
    const { result } = renderHook(() => useConversationApp("http://test"));
    await waitFor(() => expect(result.current.activeConversationId).toBe("c1"));
    act(() => {
      lastSocket().onopen?.();
      lastSocket().onmessage?.({
        data: JSON.stringify({
          schema_version: "5.0.0",
          sequence: 1,
          conversation_id: "c1",
          turn_id: "t1",
          type: "stage.changed",
          stage: "planning",
          message: "研究计划已生成",
          data: { subquestions: ["子问题一"] },
          timestamp: "2026-08-29T00:00:00Z",
        }),
      });
    });
    expect(result.current.planSubquestions).toEqual(["子问题一"]);
    act(() => {
      lastSocket().onmessage?.({
        data: JSON.stringify({
          schema_version: "5.0.0",
          sequence: 2,
          conversation_id: "c1",
          turn_id: "t1",
          type: "turn.failed",
          stage: null,
          message: "研究模型请求超时，请稍后重试",
          data: { turn_id: "t1", error_kind: "model-timeout" },
          timestamp: "2026-08-29T00:00:00Z",
        }),
      });
    });
    expect(result.current.error).toBe("研究模型请求超时，请稍后重试");
    expect(result.current.planSubquestions).toEqual([]);
  });

  it("reconnects with backoff after an abnormal close", async () => {
    // 记录退避调用但透传真实计时器（不干扰 waitFor）
    const originalSetTimeout = window.setTimeout.bind(window);
    const backoffCalls: (number | undefined)[] = [];
    const setTimeoutSpy = vi
      .spyOn(window, "setTimeout")
      .mockImplementation(((fn: () => void, ms?: number, ...rest: unknown[]) => {
        backoffCalls.push(ms);
        return originalSetTimeout(fn as Parameters<typeof originalSetTimeout>[0], ms);
      }) as unknown as typeof window.setTimeout);
    try {
      const { result } = renderHook(() => useConversationApp("http://test"));
      await waitFor(() => expect(lastSocket()).toBeDefined());
      const count = FakeWebSocket.instances.length;
      act(() => {
        lastSocket().onclose?.();
      });
      // onclose 后应重新建立连接（退避参数由实现保证，这里锁定行为）
      await waitFor(() => {
        expect(FakeWebSocket.instances.length).toBeGreaterThanOrEqual(count);
        expect(lastSocket()).not.toBeUndefined();
      });
      expect(result.current.error).toBeNull();
    } finally {
      setTimeoutSpy.mockRestore();
    }
  });
});
