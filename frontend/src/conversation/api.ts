import type { AdminUserSummary, Conversation, ConversationEvent, ConversationSummary, LibraryDocument, User } from "./contracts";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

const DEFAULT_TIMEOUT_MS = 30_000;
const UPLOAD_TIMEOUT_MS = 120_000; // 多文件解析入库可达数十秒（I2）

async function request<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  const isUpload = init?.body instanceof FormData;
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    signal: AbortSignal.timeout(isUpload ? UPLOAD_TIMEOUT_MS : DEFAULT_TIMEOUT_MS),
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
  conversationsLite: (baseUrl: string) =>
    request<ConversationSummary[]>(baseUrl, "/api/conversations/lite"),
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
  cancelTurn: (baseUrl: string, id: string, turnId: string) =>
    request<void>(baseUrl, `/api/conversations/${id}/turns/${turnId}`, {
      method: "DELETE",
    }),
  conversation: (baseUrl: string, id: string) =>
    request<Conversation>(baseUrl, `/api/conversations/${id}`),
  libraryDocuments: (baseUrl: string) =>
    request<LibraryDocument[]>(baseUrl, "/api/library/documents"),
  uploadLibraryDocuments: (baseUrl: string, files: File[]) => {
    const body = new FormData();
    files.forEach((file) => body.append("files", file));
    return request<LibraryDocument[]>(baseUrl, "/api/library/documents", {
      method: "POST",
      body,
    });
  },
  deleteLibraryDocument: (baseUrl: string, documentId: string) =>
    request<void>(baseUrl, `/api/library/documents/${documentId}`, {
      method: "DELETE",
    }),
};

export function eventSocketUrl(baseUrl: string, conversationId: string): string {
  // 同源模式（baseUrl 为空）退回当前 origin，new URL 不接受空串
  const url = new URL(baseUrl || window.location.origin);
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
