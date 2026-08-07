/**
 * Phase 2A transport helpers — native `fetch` only, frozen API paths.
 *
 * Error discipline: `requestJson` exposes only stable HTTP status/detail
 * context. Raw response text, exception reprs, secrets and absolute paths
 * never enter error messages or returned values.
 */

import {
  EVENT_TYPES,
  TUTORIAL_EVENT_VERSION,
  type EventType,
  type FileListResponse,
  type HealthInfo,
  type TaskCancelResponse,
  type TaskStartResponse,
  type TutorialEvent,
  type UploadResponse,
} from "./types";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

const MALFORMED_EVENT_MESSAGE = "Received a malformed event payload.";
const UNSUPPORTED_EVENT_MESSAGE = "Received an unsupported event payload.";
const UNSUPPORTED_VERSION_MESSAGE = "Received an unsupported event version.";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Validate a raw WebSocket text frame as TutorialEvent v1.
 *
 * Rejects malformed JSON, unknown versions, invalid shape, non-positive
 * sequence, non-UUID thread ids and unknown event types. Thrown errors are
 * stable user-safe constants and never include the raw payload.
 */
export function parseEvent(raw: string): TutorialEvent {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new Error(MALFORMED_EVENT_MESSAGE);
  }

  if (!isRecord(value)) {
    throw new Error(UNSUPPORTED_EVENT_MESSAGE);
  }
  if (value.version !== TUTORIAL_EVENT_VERSION) {
    throw new Error(UNSUPPORTED_VERSION_MESSAGE);
  }

  const { version, sequence, thread_id, type, message, data, timestamp } =
    value;
  const valid =
    version === TUTORIAL_EVENT_VERSION &&
    typeof sequence === "number" &&
    Number.isInteger(sequence) &&
    sequence > 0 &&
    typeof thread_id === "string" &&
    UUID_PATTERN.test(thread_id) &&
    typeof type === "string" &&
    (EVENT_TYPES as readonly string[]).includes(type) &&
    typeof message === "string" &&
    typeof timestamp === "string" &&
    isRecord(data);
  if (!valid) {
    throw new Error(UNSUPPORTED_EVENT_MESSAGE);
  }

  return {
    version,
    sequence,
    thread_id,
    type: type as EventType,
    message,
    data,
    timestamp,
  };
}

function normalizeBase(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, "");
}

/**
 * Parse a JSON response body and return its `detail` field when present.
 * Never exposes raw response text.
 */
async function readDetail(response: Response): Promise<string | undefined> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return undefined;
  }
  if (isRecord(body) && typeof body.detail === "string") {
    return body.detail;
  }
  return undefined;
}

/**
 * Shared JSON transport helper for the frozen Phase 2A API.
 *
 * On failure throws `HTTP <status>` (plus `: <detail>` when the server
 * returned a stable string detail). Response internals are never included.
 */
export async function requestJson(
  baseUrl: string,
  path: string,
  init?: RequestInit
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${normalizeBase(baseUrl)}${path}`, init);
  } catch {
    throw new Error("Network request failed.");
  }
  if (!response.ok) {
    const detail = await readDetail(response);
    throw new Error(
      detail ? `HTTP ${response.status}: ${detail}` : `HTTP ${response.status}`
    );
  }
  return response.json();
}

/** `GET /health` — provider/runtime modes. */
export async function health(baseUrl: string): Promise<HealthInfo> {
  return (await requestJson(baseUrl, "/health")) as HealthInfo;
}

/** `POST /api/upload` — multipart constraint upload for one thread. */
export async function uploadConstraint(
  baseUrl: string,
  threadId: string,
  file: File
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("thread_id", threadId);
  form.append("files", file);
  return (await requestJson(baseUrl, "/api/upload", {
    method: "POST",
    body: form,
  })) as UploadResponse;
}

/** `POST /api/task` — start one research task for the thread. */
export async function startTask(
  baseUrl: string,
  threadId: string,
  query: string
): Promise<TaskStartResponse> {
  return (await requestJson(baseUrl, "/api/task", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, thread_id: threadId }),
  })) as TaskStartResponse;
}

/** `POST /api/task/{thread_id}/cancel`. */
export async function cancelTask(
  baseUrl: string,
  threadId: string
): Promise<TaskCancelResponse> {
  return (await requestJson(baseUrl, `/api/task/${encodeURIComponent(threadId)}/cancel`, {
    method: "POST",
  })) as TaskCancelResponse;
}

/** `GET /api/files?thread_id=...` — current-thread output files. */
export async function listFiles(
  baseUrl: string,
  threadId: string
): Promise<FileListResponse> {
  return (await requestJson(
    baseUrl,
    `/api/files?thread_id=${encodeURIComponent(threadId)}`
  )) as FileListResponse;
}

/**
 * Reject absolute paths, separators and traversal so only the
 * server-returned relative artifact filename can reach `/api/download`.
 */
function assertRelativeArtifactPath(path: string): void {
  if (
    path === "" ||
    path.startsWith("/") ||
    path.startsWith("\\") ||
    /^[a-zA-Z]:/.test(path) ||
    path.includes("/") ||
    path.includes("\\") ||
    path === "." ||
    path === ".."
  ) {
    throw new Error("Unsupported artifact path.");
  }
}

/**
 * Build the download URL from only the API base, the current thread UUID and
 * a server-returned relative artifact path.
 */
export function downloadUrl(
  baseUrl: string,
  threadId: string,
  path: string
): string {
  assertRelativeArtifactPath(path);
  return (
    `${normalizeBase(baseUrl)}/api/download` +
    `?thread_id=${encodeURIComponent(threadId)}` +
    `&path=${encodeURIComponent(path)}`
  );
}
