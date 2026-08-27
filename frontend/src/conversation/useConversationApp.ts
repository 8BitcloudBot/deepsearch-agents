import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, conversationApi, eventSocketUrl, parseConversationEvent } from "./api";
import type { AdminUserSummary, Conversation, User } from "./contracts";
import type { ConversationWorkspaceState } from "./ConversationWorkspace";

export interface ConversationAppState extends ConversationWorkspaceState {
  booting: boolean;
  loginError: string | null;
  login: (username: string, password: string) => Promise<void>;
}

function newestId(items: Conversation[]): string | null {
  return items[0]?.id ?? null;
}

export function useConversationApp(baseUrl: string): ConversationAppState {
  const [user, setUser] = useState<User | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [adminUsers, setAdminUsers] = useState<AdminUserSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [useWeb, setUseWeb] = useState(true);
  const [stage, setStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [booting, setBooting] = useState(true);
  const socketRef = useRef<WebSocket | null>(null);

  const loadConversations = useCallback(async (preferredId?: string | null) => {
    const items = await conversationApi.conversations(baseUrl);
    setConversations(items);
    setActiveConversationId((current) => {
      const candidate = preferredId ?? current;
      return candidate && items.some((item) => item.id === candidate)
        ? candidate
        : newestId(items);
    });
  }, [baseUrl]);

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

  useEffect(() => {
    socketRef.current?.close();
    socketRef.current = null;
    if (!user || !activeConversationId) return;
    const socket = new WebSocket(eventSocketUrl(baseUrl, activeConversationId));
    socketRef.current = socket;
    socket.onmessage = (message) => {
      const event = parseConversationEvent(String(message.data));
      if (!event) return;
      if (event.type === "stage.changed" || event.type === "turn.started") {
        setStage(event.message);
      }
      if (event.type === "turn.failed") {
        setStage(null);
        setError(event.message || "本轮研究失败");
      }
      if (event.type === "turn.completed") setStage(null);
      if (["answer.delta", "evidence.ready", "report.updated", "turn.completed", "turn.failed"].includes(event.type)) {
        void loadConversations(activeConversationId);
      }
    };
    socket.onerror = () => setError("实时进度连接已中断，结果仍会保存在会话中");
    return () => socket.close();
  }, [activeConversationId, baseUrl, loadConversations, user]);

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
  }, [baseUrl, loadAdminUsers, loadConversations]);

  const logout = useCallback(async () => {
    await conversationApi.logout(baseUrl);
    socketRef.current?.close();
    setUser(null);
    setConversations([]);
    setAdminUsers([]);
    setActiveConversationId(null);
  }, [baseUrl]);

  const createConversation = useCallback(async () => {
    const created = await conversationApi.createConversation(baseUrl);
    await loadConversations(created.id);
  }, [baseUrl, loadConversations]);

  const deleteConversation = useCallback(async (id: string) => {
    await conversationApi.deleteConversation(baseUrl, id);
    await loadConversations(activeConversationId === id ? null : activeConversationId);
  }, [activeConversationId, baseUrl, loadConversations]);

  const renameConversation = useCallback(async (id: string, title: string) => {
    await conversationApi.renameConversation(baseUrl, id, title);
    await loadConversations(id);
  }, [baseUrl, loadConversations]);

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
    } catch {
      setQuestion(value);
      setStage(null);
      setError("问题未能提交，请稍后重试");
    }
  }, [activeConversationId, baseUrl, loadConversations, question, stage, useWeb]);

  return {
    user,
    conversations,
    adminUsers,
    activeConversationId,
    question,
    useWeb,
    stage,
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
    logout,
    login,
    reportUrl: (id) => `${baseUrl}/api/conversations/${id}/report`,
  };
}
