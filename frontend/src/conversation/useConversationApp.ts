import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, conversationApi, eventSocketUrl, parseConversationEvent } from "./api";
import type { AdminUserSummary, Conversation, ConversationSummary, LibraryDocument, User } from "./contracts";
import type { ConversationWorkspaceState } from "./ConversationWorkspace";

export interface ConversationAppState extends ConversationWorkspaceState {
  booting: boolean;
  loginError: string | null;
  login: (username: string, password: string) => Promise<void>;
}

const WS_MAX_RECONNECT_ATTEMPTS = 5;

function newestId(items: ConversationSummary[]): string | null {
  return items[0]?.id ?? null;
}

export function useConversationApp(baseUrl: string): ConversationAppState {
  const [user, setUser] = useState<User | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [adminUsers, setAdminUsers] = useState<AdminUserSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [useWeb, setUseWeb] = useState(true);

  const [view, setView] = useState<"research" | "library">("research");
  const [libraryDocs, setLibraryDocs] = useState<LibraryDocument[]>([]);
  const [libraryBusy, setLibraryBusy] = useState(false);
  const [stage, setStage] = useState<string | null>(null);
  const [planSubquestions, setPlanSubquestions] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [booting, setBooting] = useState(true);
  const socketRef = useRef<WebSocket | null>(null);
  const lastSequenceRef = useRef(0);

  // 统一处理会话过期的 401 拦截（G11）
  const handleApiError = useCallback((caught: unknown, fallback: string) => {
    if (caught instanceof ApiError && caught.status === 401) {
      setUser(null);
      return;
    }
    setError(fallback);
  }, []);

  const loadConversations = useCallback(async (preferredId?: string | null) => {
    // G11：列表走轻量端点（仅元数据），详情单独按需拉取
    const items = await conversationApi.conversationsLite(baseUrl);
    setConversations(items);
    setActiveConversationId((current) => {
      const candidate = preferredId ?? current;
      return candidate && items.some((item) => item.id === candidate)
        ? candidate
        : newestId(items);
    });
  }, [baseUrl]);

  const refreshActiveConversation = useCallback(async (id: string) => {
    try {
      setActiveConversation(await conversationApi.conversation(baseUrl, id));
    } catch (caught) {
      handleApiError(caught, "会话内容加载失败");
    }
  }, [baseUrl, handleApiError]);

  const loadAdminUsers = useCallback(async (role: User["role"]) => {
    if (role !== "admin") {
      setAdminUsers([]);
      return;
    }
    setAdminUsers(await conversationApi.adminUsers(baseUrl));
  }, [baseUrl]);

  useEffect(() => {
    let active = true;
    void conversationApi.me(baseUrl)
      .then(async (value) => {
        if (!active) return;
        setUser(value);
        await loadConversations();
        await loadAdminUsers(value.role);
      })
      .catch((caught: unknown) => {
        if (active && !(caught instanceof ApiError && caught.status === 401)) {
          setError("无法连接研究服务");
        }
      })
      .finally(() => active && setBooting(false));
    return () => { active = false; };
  }, [baseUrl, loadAdminUsers, loadConversations]);

  // 激活会话变化 → 拉取该会话完整详情
  useEffect(() => {
    lastSequenceRef.current = 0;
    if (!user || !activeConversationId) {
      setActiveConversation(null);
      return;
    }
    void refreshActiveConversation(activeConversationId);
  }, [activeConversationId, refreshActiveConversation, user]);

  useEffect(() => {
    socketRef.current?.close();
    socketRef.current = null;
    if (!user || !activeConversationId) return;
    let disposed = false;
    let attempts = 0;
    let reconnectTimer: number | undefined;
    let socket: WebSocket | null = null;

    const connect = () => {
      if (disposed) return;
      socket = new WebSocket(eventSocketUrl(baseUrl, activeConversationId));
      socketRef.current = socket;
      socket.onopen = () => {
        attempts = 0;
      };
      socket.onmessage = (message) => {
        const event = parseConversationEvent(String(message.data));
        if (!event) return;
        if (event.sequence > lastSequenceRef.current + 1) {
          console.warn("conversation events skipped", lastSequenceRef.current, event.sequence);
        }
        lastSequenceRef.current = event.sequence;
        if (event.type === "stage.changed" || event.type === "turn.started") {
          setStage(event.message);
          const subquestions = event.data?.subquestions;
          if (Array.isArray(subquestions)) {
            setPlanSubquestions(subquestions.filter((item): item is string => typeof item === "string"));
          }
        }
        if (event.type === "turn.failed") {
          setStage(null);
          setPlanSubquestions([]);
          setError(event.message || "本轮研究失败");
        }
        if (event.type === "turn.completed") {
          setStage(null);
          setPlanSubquestions([]);
        }
        // G11：回合事件只增量刷新当前会话详情；列表用轻量端点
        if (
          ["answer.delta", "evidence.ready", "report.updated", "turn.completed", "turn.failed"]
            .includes(event.type)
        ) {
          void refreshActiveConversation(activeConversationId);
          void loadConversations(activeConversationId).catch(() => {});
        }
      };
      socket.onclose = () => {
        if (disposed) return;
        if (attempts < WS_MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(8000, 500 * 2 ** attempts);
          attempts += 1;
          reconnectTimer = window.setTimeout(connect, delay);
        } else {
          setError("实时进度连接已中断，结果仍会保存在会话中");
        }
      };
      socket.onerror = () => { /* 统一由 onclose 处理 */ };
    };
    connect();
    return () => {
      disposed = true;
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [activeConversationId, baseUrl, loadConversations, refreshActiveConversation, user]);

  const login = useCallback(async (username: string, password: string) => {
    setLoginError(null);
    try {
      const response = await conversationApi.login(baseUrl, username, password);
      setUser(response.user);
      await loadConversations();
      await loadAdminUsers(response.user.role);
    } catch {
      setLoginError("用户名或密码不正确");
    }
  }, [baseUrl, loadConversations, loadAdminUsers]);

  const logout = useCallback(async () => {
    await conversationApi.logout(baseUrl);
    socketRef.current?.close();
    setUser(null);
    setConversations([]);
    setActiveConversation(null);
    setAdminUsers([]);
    setActiveConversationId(null);
  }, [baseUrl]);

  const createConversation = useCallback(async () => {
    const created = await conversationApi.createConversation(baseUrl);
    await loadConversations(created.id);
  }, [baseUrl, loadConversations]);

  const deleteConversation = useCallback(async (id: string) => {
    await conversationApi.deleteConversation(baseUrl, id);
    if (activeConversationId === id) setActiveConversation(null);
    await loadConversations(activeConversationId === id ? null : activeConversationId);
  }, [activeConversationId, baseUrl, loadConversations]);

  const renameConversation = useCallback(async (id: string, title: string) => {
    await conversationApi.renameConversation(baseUrl, id, title);
    await loadConversations(id);
    if (activeConversationId === id) void refreshActiveConversation(id);
  }, [activeConversationId, baseUrl, loadConversations, refreshActiveConversation]);

  const resetUserData = useCallback(async (userId: string) => {
    await conversationApi.resetUserData(baseUrl, userId);
    await Promise.all([loadConversations(), loadAdminUsers("admin")]);
  }, [baseUrl, loadAdminUsers, loadConversations]);

  const submitTurn = useCallback(async () => {
    const value = question.trim();
    if (!activeConversationId || !value || stage) return;
    setQuestion("");
    setError(null);
    setStage("分析问题");
    try {
      await conversationApi.submitTurn(baseUrl, activeConversationId, value, useWeb);
      await loadConversations(activeConversationId);
    } catch (caught) {
      setQuestion(value);
      setStage(null);
      handleApiError(caught, "问题未能提交，请稍后重试");
    }
  }, [activeConversationId, baseUrl, handleApiError, loadConversations, question, stage, useWeb]);


  const loadLibrary = useCallback(async () => {
    try {
      setLibraryDocs(await conversationApi.libraryDocuments(baseUrl));
    } catch {
      /* 个人知识库不可用时静默降级为空列表 */
      setLibraryDocs([]);
    }
  }, [baseUrl]);

  useEffect(() => {
    if (user) void loadLibrary();
  }, [user, loadLibrary]);

  const uploadLibraryDocuments = useCallback(
    async (files: File[]) => {
      if (files.length === 0 || libraryBusy) return;
      setLibraryBusy(true);
      try {
        await conversationApi.uploadLibraryDocuments(baseUrl, files);
        await loadLibrary();
      } catch (error_) {
        if (error_ instanceof ApiError && error_.status === 401) {
          setUser(null);
        } else {
          setError(error_ instanceof ApiError ? error_.message : "入库失败，请稍后重试");
        }
      } finally {
        setLibraryBusy(false);
      }
    },
    [baseUrl, libraryBusy, loadLibrary],
  );

  const deleteLibraryDocument = useCallback(
    async (documentId: string) => {
      try {
        await conversationApi.deleteLibraryDocument(baseUrl, documentId);
        await loadLibrary();
      } catch (error_) {
        if (error_ instanceof ApiError && error_.status === 401) {
          setUser(null);
        } else {
          setError(error_ instanceof ApiError ? error_.message : "删除失败，请稍后重试");
        }
      } finally {
        void loadLibrary();
      }
    },
    [baseUrl, loadLibrary],
  );

  return {
    user,
    conversations: conversations as Conversation[],
    activeConversation,
    adminUsers,
    activeConversationId,
    question,
    useWeb,
    stage,
    planSubquestions,
    error,
    booting,
    loginError,
    setQuestion,
    setUseWeb,
    selectConversation: setActiveConversationId,
    createConversation,
    deleteConversation,
    renameConversation,
    resetUserData,
    submitTurn,
    view,
    setView,
    libraryDocs,
    libraryBusy,
    uploadLibraryDocuments,
    deleteLibraryDocument,
    logout,
    login,
    reportUrl: (id) => `${baseUrl}/api/conversations/${id}/report`,
  };
}
