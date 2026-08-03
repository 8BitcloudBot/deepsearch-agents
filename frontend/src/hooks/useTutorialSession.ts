/**
 * Single-session tutorial workbench hook.
 *
 * Contract (locked with app/api):
 *  - a fresh UUID thread_id is minted per session;
 *  - run() opens the WebSocket at /ws/{thread_id} first and only POSTs
 *    /api/task once the socket is open;
 *  - a {"type":"ping"} heartbeat is sent every HEARTBEAT_INTERVAL_MS while
 *    the socket is open; {"type":"pong"} replies never enter the feed;
 *  - frames that fail the strict TutorialEvent schema are dropped;
 *  - a terminal event (task_completed / task_cancelled / task_failed) sets
 *    the session status and refreshes the artifact list from /api/files.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  cancelTask,
  listFiles,
  postTask,
  uploadFiles,
  wsUrl,
} from "../lib/api";
import {
  isHeartbeatMessage,
  isTutorialEvent,
  TERMINAL_EVENT_TYPES,
  type FileInfo,
  type SessionStatus,
  type TutorialEvent,
  type UploadFileInfo,
} from "../types";

export const HEARTBEAT_INTERVAL_MS = 25_000;

const TERMINAL_STATUS: Record<string, SessionStatus> = {
  task_completed: "completed",
  task_cancelled: "cancelled",
  task_failed: "failed",
};

function newThreadId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export interface TutorialSession {
  threadId: string;
  status: SessionStatus;
  events: TutorialEvent[];
  artifacts: FileInfo[];
  uploadedFiles: UploadFileInfo[];
  error: string | null;
  run: (query: string) => Promise<void>;
  cancel: () => Promise<void>;
  upload: (files: File[]) => Promise<void>;
}

export function useTutorialSession(baseUrl: string): TutorialSession {
  const threadId = useMemo(newThreadId, []);
  const [status, setStatus] = useState<SessionStatus>("idle");
  const [events, setEvents] = useState<TutorialEvent[]>([]);
  const [artifacts, setArtifacts] = useState<FileInfo[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<UploadFileInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const statusRef = useRef<SessionStatus>("idle");

  const updateStatus = useCallback((next: SessionStatus) => {
    statusRef.current = next;
    setStatus(next);
  }, []);

  const clearHeartbeat = useCallback(() => {
    if (heartbeatRef.current !== null) {
      window.clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const closeSocket = useCallback(() => {
    clearHeartbeat();
    if (wsRef.current) {
      const ws = wsRef.current;
      wsRef.current = null;
      ws.close();
    }
  }, [clearHeartbeat]);

  const refreshArtifacts = useCallback(async () => {
    try {
      setArtifacts(await listFiles(baseUrl, threadId));
    } catch {
      // Terminal state is already set; artifact refresh is best-effort.
    }
  }, [baseUrl, threadId]);

  const run = useCallback(
    (query: string): Promise<void> => {
      if (!query.trim() || wsRef.current) return Promise.resolve();
      setEvents([]);
      setArtifacts([]);
      setError(null);
      updateStatus("connecting");

      const ws = new WebSocket(wsUrl(baseUrl, threadId));
      wsRef.current = ws;

      return new Promise<void>((resolve) => {
        ws.onopen = () => {
          if (wsRef.current !== ws) return;
          heartbeatRef.current = window.setInterval(() => {
            // WebSocket.OPEN === 1; compare against the literal so test doubles
            // without static constants behave identically.
            if (ws.readyState === 1) {
              ws.send(JSON.stringify({ type: "ping" }));
            }
          }, HEARTBEAT_INTERVAL_MS);
          void postTask(baseUrl, query, threadId)
            .then(() => {
              // The socket may have closed while the POST was in flight; do
              // not overwrite an error state with "running".
              if (wsRef.current === ws && ws.readyState === 1) {
                updateStatus("running");
              }
            })
            .catch((err: unknown) => {
              if (wsRef.current === ws) {
                updateStatus("error");
                setError(err instanceof Error ? err.message : String(err));
                // Release the socket so a later Run can open a fresh one;
                // onclose sees status "error" and keeps the error message.
                closeSocket();
              }
            })
            .finally(() => resolve());
        };

        ws.onmessage = (ev: MessageEvent) => {
          let parsed: unknown;
          try {
            parsed = JSON.parse(String(ev.data));
          } catch {
            return; // Non-JSON frames are rejected.
          }
          if (isHeartbeatMessage(parsed)) return; // pong never enters the feed.
          if (!isTutorialEvent(parsed)) return; // Schema-invalid frames are dropped.
          setEvents((prev) => [...prev, parsed]);
          if (TERMINAL_EVENT_TYPES.includes(parsed.type)) {
            updateStatus(TERMINAL_STATUS[parsed.type] ?? "error");
            void refreshArtifacts();
            // The run is over: release the socket so the next task can start.
            closeSocket();
          }
        };

        ws.onerror = () => {
          ws.close();
        };

        ws.onclose = () => {
          clearHeartbeat();
          if (
            statusRef.current === "connecting" ||
            statusRef.current === "running"
          ) {
            updateStatus("error");
            setError("connection closed");
          }
          resolve();
        };
      });
    },
    [baseUrl, clearHeartbeat, closeSocket, refreshArtifacts, threadId, updateStatus]
  );

  const cancel = useCallback(async () => {
    try {
      const res = await cancelTask(baseUrl, threadId);
      if (res.status === "cancelled" || res.status === "cancelling") {
        updateStatus("cancelled");
        closeSocket();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [baseUrl, closeSocket, threadId, updateStatus]);

  const upload = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;
      try {
        const res = await uploadFiles(baseUrl, threadId, files);
        setUploadedFiles(res.files);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [baseUrl, threadId]
  );

  useEffect(() => {
    return () => {
      closeSocket();
    };
  }, [closeSocket]);

  return {
    threadId,
    status,
    events,
    artifacts,
    uploadedFiles,
    error,
    run,
    cancel,
    upload,
  };
}
