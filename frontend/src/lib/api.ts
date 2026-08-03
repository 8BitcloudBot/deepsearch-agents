/**
 * Phase 2 locked HTTP/WebSocket client — mirrors app/api/server.py.
 * Endpoints: POST /api/task, POST /api/task/{id}/cancel, POST /api/upload,
 * GET /api/files, GET /api/download, WS /ws/{thread_id}.
 */
import type {
  FileInfo,
  TaskCancelResponse,
  TaskStartResponse,
  UploadResponse,
} from "../types";

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ||
  "http://127.0.0.1:8000";

/** WebSocket URL for a thread (http -> ws, https -> wss). */
export function wsUrl(baseUrl: string, threadId: string): string {
  const url = new URL(baseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `${url.pathname.replace(/\/+$/, "")}/ws/${threadId}`;
  return url.toString();
}

/** Download URL with both query parameters URI-encoded. */
export function downloadUrl(threadId: string, path: string): string {
  return `${API_BASE_URL}/api/download?thread_id=${encodeURIComponent(
    threadId
  )}&path=${encodeURIComponent(path)}`;
}

async function jsonOrThrow<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(
      `${label} failed (HTTP ${res.status}${detail ? `: ${detail}` : ""})`
    );
  }
  return (await res.json()) as T;
}

export async function postTask(
  baseUrl: string,
  query: string,
  threadId: string
): Promise<TaskStartResponse> {
  const res = await fetch(`${baseUrl}/api/task`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, thread_id: threadId }),
  });
  return jsonOrThrow<TaskStartResponse>(res, "task start");
}

export async function cancelTask(
  baseUrl: string,
  threadId: string
): Promise<TaskCancelResponse> {
  const res = await fetch(`${baseUrl}/api/task/${threadId}/cancel`, {
    method: "POST",
  });
  return jsonOrThrow<TaskCancelResponse>(res, "task cancel");
}

export async function uploadFiles(
  baseUrl: string,
  threadId: string,
  files: File[]
): Promise<UploadResponse> {
  const body = new FormData();
  body.append("thread_id", threadId);
  for (const file of files) {
    body.append("files", file);
  }
  const res = await fetch(`${baseUrl}/api/upload`, {
    method: "POST",
    body,
  });
  return jsonOrThrow<UploadResponse>(res, "upload");
}

export async function listFiles(
  baseUrl: string,
  threadId: string
): Promise<FileInfo[]> {
  const res = await fetch(
    `${baseUrl}/api/files?thread_id=${encodeURIComponent(threadId)}`
  );
  const data = await jsonOrThrow<{ thread_id: string; files: FileInfo[] }>(
    res,
    "files list"
  );
  return data.files;
}

export async function fetchText(url: string): Promise<string> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`download failed (HTTP ${res.status})`);
  }
  return res.text();
}
