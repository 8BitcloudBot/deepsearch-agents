/**
 * Phase 2 locked contracts — mirror of app/api/schemas.py and app/api/events.py.
 * Do not widen these shapes: the backend validates them strictly.
 */

export type TutorialEventType =
  | "task_started"
  | "agent_started"
  | "agent_completed"
  | "tool_started"
  | "tool_completed"
  | "artifact_created"
  | "task_completed"
  | "task_cancelled"
  | "task_failed";

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

/** Single event pushed by the server over /ws/{thread_id}. */
export interface TutorialEvent {
  version: 1;
  sequence: number;
  thread_id: string;
  type: TutorialEventType;
  message: string;
  data: Record<string, JsonValue>;
  timestamp: string;
}

/** Server reply to a client {"type":"ping"} heartbeat. */
export interface HeartbeatMessage {
  type: "pong";
}

export const TERMINAL_EVENT_TYPES: readonly TutorialEventType[] = [
  "task_completed",
  "task_cancelled",
  "task_failed",
];

const TUTORIAL_EVENT_TYPES: ReadonlySet<string> = new Set([
  "task_started",
  "agent_started",
  "agent_completed",
  "tool_started",
  "tool_completed",
  "artifact_created",
  "task_completed",
  "task_cancelled",
  "task_failed",
]);

function isJsonValue(value: unknown): value is JsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return true;
  }
  if (typeof value === "number") {
    return Number.isFinite(value);
  }
  if (Array.isArray(value)) {
    return value.every(isJsonValue);
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).every(
      ([, val]) => isJsonValue(val)
    );
  }
  return false;
}

/** Strict schema gate — only fully valid TutorialEvent objects pass. */
export function isTutorialEvent(value: unknown): value is TutorialEvent {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const v = value as Record<string, unknown>;
  return (
    v.version === 1 &&
    typeof v.sequence === "number" &&
    Number.isInteger(v.sequence) &&
    v.sequence >= 1 &&
    typeof v.thread_id === "string" &&
    typeof v.type === "string" &&
    TUTORIAL_EVENT_TYPES.has(v.type) &&
    typeof v.message === "string" &&
    typeof v.timestamp === "string" &&
    typeof v.data === "object" &&
    v.data !== null &&
    !Array.isArray(v.data) &&
    isJsonValue(v.data)
  );
}

export function isHeartbeatMessage(value: unknown): value is HeartbeatMessage {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as { type?: unknown }).type === "pong"
  );
}

// ── HTTP contract types ────────────────────────────────────────────────

export interface TaskStartResponse {
  status: "started";
  thread_id: string;
}

export interface TaskCancelResponse {
  thread_id: string;
  status: "cancelled" | "cancelling" | "not_found";
}

export interface UploadFileInfo {
  name: string;
  size: number;
}

export interface UploadResponse {
  status: "uploaded";
  thread_id: string;
  files: UploadFileInfo[];
}

export interface FileInfo {
  name: string;
  path: string;
  size: number;
  media_type: string;
}

export interface FileListResponse {
  thread_id: string;
  files: FileInfo[];
}

export type SessionStatus =
  | "idle"
  | "connecting"
  | "running"
  | "completed"
  | "cancelled"
  | "failed"
  | "error";
