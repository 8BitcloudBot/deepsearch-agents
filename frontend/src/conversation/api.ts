import type { AdminUserSummary, Conversation, ConversationEvent, User } from "./contracts";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

async function request<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: init?.body instanceof FormData
      ? init.headers
      : { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let message = "请求失败";
    try {
      const payload = await response.json() as { detail?: string };
      message = payload.detail || message;
    } catch {
      // The status remains the reliable part of a non-JSON response.
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const conversationApi = {
  login: (baseUrl: string, username: string, password: string) =>
    request<{ user: User }>(baseUrl, "/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: (baseUrl: string) =>
    request<void>(baseUrl, "/api/auth/logout", { method: "POST" }),
  me: (baseUrl: string) => request<User>(baseUrl, "/api/auth/me"),
  adminUsers: (baseUrl: string) =>
    request<AdminUserSummary[]>(baseUrl, "/api/admin/users"),
  resetUserData: (baseUrl: string, userId: string) =>
    request<void>(baseUrl, `/api/admin/users/${userId}/data`, { method: "DELETE" }),
  conversations: (baseUrl: string) =>
    request<Conversation[]>(baseUrl, "/api/conversations"),
  createConversation: (baseUrl: string, title = "新研究") =>
    request<Conversation>(baseUrl, "/api/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  renameConversation: (baseUrl: string, id: string, title: string) =>
    request<Conversation>(baseUrl, `/api/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  deleteConversation: (baseUrl: string, id: string) =>
    request<void>(baseUrl, `/api/conversations/${id}`, { method: "DELETE" }),
  submitTurn: (baseUrl: string, id: string, question: string, useWeb: boolean) =>
    request<{ turn_id: string }>(baseUrl, `/api/conversations/${id}/turns`, {
      method: "POST",
      body: JSON.stringify({ question, use_web: useWeb }),
    }),
  conversation: (baseUrl: string, id: string) =>
    request<Conversation>(baseUrl, `/api/conversations/${id}`),
};

export function eventSocketUrl(baseUrl: string, conversationId: string): string {
  const url = new URL(baseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `/api/conversations/${conversationId}/events`;
  url.search = "";
  return url.toString();
}

export function parseConversationEvent(value: string): ConversationEvent | null {
  try {
    const event = JSON.parse(value) as Partial<ConversationEvent>;
    if (event.schema_version !== "5.0.0" || typeof event.type !== "string") return null;
    return event as ConversationEvent;
  } catch {
    return null;
  }
}
