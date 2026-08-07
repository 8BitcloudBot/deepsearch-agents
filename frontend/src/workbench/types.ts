/**
 * Phase 2A frontend contracts — frozen by docs/phases/phase-2a-implementation-addendum.md.
 *
 * These types mirror the accepted backend schemas (app/api/schemas.py) and the
 * TutorialEvent v1 WebSocket contract. No persistence, replay or future-API
 * fields are modeled here.
 */

export const TUTORIAL_EVENT_VERSION = 1 as const;

export const EVENT_TYPES = [
  "task_started",
  "agent_started",
  "agent_completed",
  "tool_started",
  "tool_completed",
  "artifact_created",
  "task_completed",
  "task_cancelled",
  "task_failed",
] as const;

export type EventType = (typeof EVENT_TYPES)[number];

/** TutorialEvent version 1 as delivered by the `/ws/{thread_id}` stream. */
export interface TutorialEvent {
  version: typeof TUTORIAL_EVENT_VERSION;
  sequence: number;
  thread_id: string;
  type: EventType;
  message: string;
  /** JSON-compatible payload; never treated as UI markup. */
  data: Record<string, unknown>;
  /** ISO-8601 timestamp string emitted by the backend. */
  timestamp: string;
}

/** Workbench run status union required by the Phase 2A UI. */
export type RunStatus =
  | "idle"
  | "uploading"
  | "ready"
  | "running"
  | "success"
  | "failed"
  | "cancelled"
  | "connection-error";

/** `GET /health` — non-secret provider/runtime modes. */
export interface HealthInfo {
  status: string;
  service: string;
  phase: string;
  tutorial_profile: string;
  tutorial_runtime: string;
  web_provider: string;
  catalog_provider: string;
  knowledge_provider: string;
}

export interface UploadFileInfo {
  name: string;
  size: number;
}

/** `POST /api/upload` response. */
export interface UploadResponse {
  status: "uploaded";
  thread_id: string;
  files: UploadFileInfo[];
}

/** `POST /api/task` response (HTTP 202). */
export interface TaskStartResponse {
  status: "started";
  thread_id: string;
}

/** `POST /api/task/{thread_id}/cancel` response. */
export interface TaskCancelResponse {
  thread_id: string;
  status: "cancelled" | "cancelling";
}

/** One output artifact as returned by `GET /api/files`. */
export interface FileInfo {
  name: string;
  /** Server-returned relative path — the only download input allowed. */
  path: string;
  size: number;
  media_type: string;
}

/** `GET /api/files?thread_id=...` response. */
export interface FileListResponse {
  thread_id: string;
  files: FileInfo[];
}
