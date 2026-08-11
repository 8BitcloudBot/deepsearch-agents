/**
 * Phase 2A workbench session state (slices F2/F3/F4).
 *
 * Owns one client-generated thread UUID per session, loads non-secret
 * provider/runtime modes from `/health`, and keeps one WebSocket per session
 * thread connected before any task action. F3 provides the real multipart
 * upload, task start/cancel calls and the live event timeline with an
 * exactly-once terminal guard. F4 refreshes `/api/files` on `task_completed`,
 * previews Markdown as plain text through `/api/download`, and exposes
 * Markdown/PDF download URLs built only from server-returned relative paths.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  cancelTask,
  downloadUrl,
  getCitations,
  getLiveCitations,
  health,
  listFiles,
  parseCitationCompletedData,
  parseEvent,
  LIVE_CITATION_UNAVAILABLE_MESSAGE,
  startTask,
  uploadConstraint,
} from "./api";
import type {
  CitationCompletedData,
  CitationReport,
  FileInfo,
  HealthInfo,
  LiveCitationDocument,
  LiveCitationProgress,
  LiveDeliveryStatus,
  RunStatus,
  TutorialEvent,
  UploadFileInfo,
} from "./types";

export type ConnectionState = "connecting" | "open" | "closed" | "error";

export interface WorkbenchState {
  // Session identity and server context.
  threadId: string;
  health: HealthInfo | null;
  healthError: string | null;
  connectionState: ConnectionState;
  newSession: () => void;
  // Composer inputs.
  query: string;
  setQuery: (query: string) => void;
  selectedFile: File | null;
  selectFile: (file: File | null) => void;
  uploadedFile: UploadFileInfo | null;
  upload: () => void;
  submit: () => void;
  cancel: () => void;
  // Run state — F3 populates status/error/events/terminalEvent.
  status: RunStatus;
  error: string | null;
  events: TutorialEvent[];
  terminalEvent: TutorialEvent | null;
  // True while POST /api/task is in flight; App disables start/upload on it.
  taskStartPending: boolean;
  // F4 state — current-thread artifacts and plain-text Markdown preview.
  files: FileInfo[];
  markdown: string | null;
  /** Stable preview-unavailable message; success status is preserved. */
  markdownError: string | null;
  refreshArtifacts: () => void;
  // P4-5 citation state — validated report, summary and stable error.
  citationSummary: CitationCompletedData | null;
  citations: CitationReport | null;
  citationsLoading: boolean;
  citationsError: string | null;
  // P4.5 live citation state — showcase profile only.
  liveDocument: LiveCitationDocument | null;
  liveLoading: boolean;
  liveError: string | null;
  liveDeliveryStatus: LiveDeliveryStatus;
  liveProgress: LiveCitationProgress | null;
}

const SLOW_CONSUMER_MESSAGE =
  "Event stream interrupted because the consumer was too slow.";
const CONNECTION_LOST_MESSAGE = "Connection lost before the task finished.";
const CONNECTION_FAILED_MESSAGE = "Event stream connection failed.";
const UPLOAD_FAILED_MESSAGE = "Upload failed.";
const PREVIEW_UNAVAILABLE_MESSAGE = "Preview unavailable.";
const CITATION_UNAVAILABLE_MESSAGE = "Citation results are unavailable.";

/** Create exactly one UUID per session. */
function createThreadId(): string {
  return crypto.randomUUID();
}

/** `/ws/{thread_id}` for the active thread, from the API base URL. */
function toWebSocketUrl(baseUrl: string, threadId: string): string {
  const normalized = baseUrl.replace(/\/+$/, "").replace(/^http/, "ws");
  return `${normalized}/ws/${threadId}`;
}

/** Ping/pong frames are transport heartbeats, not timeline events. */
function isHeartbeat(raw: string): boolean {
  try {
    const value: unknown = JSON.parse(raw);
    return (
      typeof value === "object" &&
      value !== null &&
      !Array.isArray(value) &&
      (value as Record<string, unknown>).type === "pong"
    );
  } catch {
    return false;
  }
}

/** Stable user-safe message: Error messages are already vetted by helpers. */
function stableMessage(cause: unknown, fallback: string): string {
  return cause instanceof Error && cause.message !== ""
    ? cause.message
    : fallback;
}

function parseLiveProgress(data: Record<string, unknown>): LiveCitationProgress | null {
  const claimCount = data.claim_count;
  const evidenceCount = data.evidence_count;
  if (
    typeof claimCount !== "number" ||
    !Number.isInteger(claimCount) ||
    claimCount < 0 ||
    typeof evidenceCount !== "number" ||
    !Number.isInteger(evidenceCount) ||
    evidenceCount < 0
  ) {
    return null;
  }
  return { claimCount, evidenceCount };
}

function parseLiveCompletion(
  data: Record<string, unknown>
): "completed" | "degraded" | null {
  return data.status === "completed" || data.status === "degraded"
    ? data.status
    : null;
}

export function useWorkbench(apiBaseUrl: string): WorkbenchState {
  const [threadId, setThreadId] = useState<string>(createThreadId);
  const [healthInfo, setHealthInfo] = useState<HealthInfo | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("connecting");
  const [query, setQueryState] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadedFile, setUploadedFile] = useState<UploadFileInfo | null>(null);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [taskStartPending, setTaskStartPending] = useState<boolean>(false);
  const [events, setEvents] = useState<TutorialEvent[]>([]);
  const [terminalEvent, setTerminalEvent] = useState<TutorialEvent | null>(null);
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [markdownError, setMarkdownError] = useState<string | null>(null);
  const [citationSummary, setCitationSummary] =
    useState<CitationCompletedData | null>(null);
  const [citations, setCitations] = useState<CitationReport | null>(null);
  const [citationsLoading, setCitationsLoading] = useState<boolean>(false);
  const [citationsError, setCitationsError] = useState<string | null>(null);
  const [liveDocument, setLiveDocument] =
    useState<LiveCitationDocument | null>(null);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [liveDeliveryStatus, setLiveDeliveryStatus] =
    useState<LiveDeliveryStatus>("idle");
  const [liveProgress, setLiveProgress] =
    useState<LiveCitationProgress | null>(null);
  // The accepted terminal event guard: later events stay visible but cannot
  // change the terminal status once this is set.
  const terminalRef = useRef<TutorialEvent | null>(null);
  // Incremented on every new session; async continuations check it so a late
  // response can never write state that belongs to a replaced thread.
  const sessionRef = useRef(0);
  // Incremented on every new run; artifact refresh continuations check it so
  // a late response cannot repopulate a cleared run.
  const runRef = useRef(0);
  const profileRef = useRef<HealthInfo["app_profile"] | null>(null);

  // Load non-secret provider/runtime modes once on mount.
  useEffect(() => {
    let cancelled = false;
    health(apiBaseUrl)
      .then((info) => {
        if (!cancelled) {
          setHealthInfo(info);
          profileRef.current = info.app_profile;
          setHealthError(null);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setHealthError(
            cause instanceof Error ? cause.message : "Health check failed."
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl]);

  /**
   * Refresh the current thread's artifact list and plain-text Markdown
   * preview. Only server-returned entries whose relative path is safe for
   * `/api/download` are kept; separators and traversal are skipped entirely.
   * Failures keep the accepted success status and surface only a stable
   * preview-unavailable message — never raw bodies or status internals.
   */
  const refreshArtifacts = useCallback(() => {
    const currentThreadId = threadId;
    const session = sessionRef.current;
    const run = runRef.current;
    listFiles(apiBaseUrl, currentThreadId)
      .then((response) => {
        if (sessionRef.current !== session || runRef.current !== run) return;
        // Only the current thread's server-returned listing is accepted.
        if (response.thread_id !== currentThreadId) {
          setFiles([]);
          setMarkdown(null);
          setMarkdownError(null);
          return;
        }
        const safeFiles = (response.files ?? []).filter((file) => {
          try {
            downloadUrl(apiBaseUrl, currentThreadId, file.path);
            return true;
          } catch {
            return false;
          }
        });
        setFiles(safeFiles);
        const markdownName =
          profileRef.current === "showcase"
            ? "showcase-report.md"
            : "tutorial-report.md";
        const markdownFile = safeFiles.find(
          (file) => file.name === markdownName || file.path === markdownName
        );
        if (!markdownFile) {
          setMarkdown(null);
          setMarkdownError(null);
          return;
        }
        // Fetch the report as plain text through /api/download; the
        // server-returned relative path is the only input. Never innerHTML.
        setMarkdown(null);
        setMarkdownError(null);
        fetch(downloadUrl(apiBaseUrl, currentThreadId, markdownFile.path))
          .then((response) => {
            if (sessionRef.current !== session || runRef.current !== run) {
              return undefined;
            }
            if (!response.ok) {
              setMarkdownError(PREVIEW_UNAVAILABLE_MESSAGE);
              return undefined;
            }
            return response.text();
          })
          .then((text) => {
            if (sessionRef.current !== session || runRef.current !== run) {
              return;
            }
            if (text !== undefined) setMarkdown(text);
          })
          .catch(() => {
            if (sessionRef.current !== session || runRef.current !== run) {
              return;
            }
            setMarkdownError(PREVIEW_UNAVAILABLE_MESSAGE);
          });
      })
      .catch(() => {
        if (sessionRef.current !== session || runRef.current !== run) return;
        setFiles([]);
        setMarkdown(null);
        setMarkdownError(PREVIEW_UNAVAILABLE_MESSAGE);
      });
  }, [apiBaseUrl, threadId]);

  const fetchLiveCitations = useCallback(() => {
    const currentThreadId = threadId;
    const session = sessionRef.current;
    const run = runRef.current;
    setLiveLoading(true);
    setLiveError(null);
    setLiveDeliveryStatus("loading");
    getLiveCitations(apiBaseUrl, currentThreadId)
      .then((document) => {
        if (sessionRef.current !== session || runRef.current !== run) return;
        if (document.thread_id !== currentThreadId) throw new Error("thread mismatch");
        setLiveDocument(document);
        setLiveLoading(false);
        setLiveDeliveryStatus("completed");
      })
      .catch(() => {
        if (sessionRef.current !== session || runRef.current !== run) return;
        setLiveDocument(null);
        setLiveLoading(false);
        setLiveDeliveryStatus("degraded");
        setLiveError(LIVE_CITATION_UNAVAILABLE_MESSAGE);
      });
  }, [apiBaseUrl, threadId]);

  /**
   * Load the validated citation report for the current thread. Triggered by
   * a `citation_completed` event with status `completed`; failures surface
   * only a stable message and never a partial report.
   */
  const fetchCitations = useCallback(() => {
    const currentThreadId = threadId;
    const session = sessionRef.current;
    const run = runRef.current;
    setCitationsLoading(true);
    setCitationsError(null);
    getCitations(apiBaseUrl, currentThreadId)
      .then((response) => {
        if (sessionRef.current !== session || runRef.current !== run) return;
        if (response.thread_id !== currentThreadId) {
          setCitations(null);
          setCitationsLoading(false);
          return;
        }
        setCitations(response.report);
        setCitationsLoading(false);
      })
      .catch((cause: unknown) => {
        if (sessionRef.current !== session || runRef.current !== run) return;
        setCitations(null);
        setCitationsLoading(false);
        setCitationsError(stableMessage(cause, CITATION_UNAVAILABLE_MESSAGE));
      });
  }, [apiBaseUrl, threadId]);

  // One WebSocket per session thread, opened before any task action. The
  // cleanup closes the old socket on reset or unmount.
  useEffect(() => {
    let socket: WebSocket | null = null;
    let cancelled = false;
    setConnectionState("connecting");
    try {
      socket = new WebSocket(toWebSocketUrl(apiBaseUrl, threadId));
      socket.onopen = () => {
        if (!cancelled) setConnectionState("open");
      };
      socket.onclose = (event: CloseEvent) => {
        if (cancelled) return;
        setConnectionState("closed");
        // A disconnect after an accepted terminal event preserves the
        // terminal status; otherwise it is an explicit connection error.
        if (terminalRef.current !== null) return;
        setStatus("connection-error");
        setError(
          event.code === 1013 ? SLOW_CONSUMER_MESSAGE : CONNECTION_LOST_MESSAGE
        );
      };
      socket.onerror = () => {
        if (cancelled) return;
        setConnectionState("error");
        // Browsers may fire error without a close; surface a visible stable
        // failure unless a terminal event already settled the run.
        if (terminalRef.current !== null) return;
        setStatus("connection-error");
        setError(CONNECTION_FAILED_MESSAGE);
      };
      socket.onmessage = (event: MessageEvent) => {
        if (cancelled) return;
        const raw = typeof event.data === "string" ? event.data : "";
        if (raw === "" || isHeartbeat(raw)) return;
        let parsed: TutorialEvent;
        try {
          parsed = parseEvent(raw);
        } catch (cause) {
          setError(
            stableMessage(cause, "Received an unsupported event payload.")
          );
          return;
        }
        // Only the current thread's events belong on this timeline.
        if (parsed.thread_id !== threadId) return;
        setEvents((previous) => {
          if (
            previous.some(
              (entry) =>
                entry.thread_id === parsed.thread_id &&
                entry.sequence === parsed.sequence
            )
          ) {
            return previous;
          }
          return [...previous, parsed].sort((a, b) => a.sequence - b.sequence);
        });
        if (terminalRef.current !== null) return;
        switch (parsed.type) {
          case "task_started":
            setStatus("running");
            break;
          case "citation_started": {
            if (profileRef.current !== "showcase") break;
            const progress = parseLiveProgress(parsed.data);
            if (progress !== null) setLiveProgress(progress);
            break;
          }
          case "citation_completed": {
            if (profileRef.current === "showcase") {
              const completion = parseLiveCompletion(parsed.data);
              if (completion === null) break;
              if (completion === "completed") {
                fetchLiveCitations();
              } else {
                setLiveLoading(false);
                setLiveDeliveryStatus("degraded");
                setLiveDocument(null);
                setLiveError("Live citation delivery did not complete.");
              }
              break;
            }
            if (profileRef.current !== "agent-research") break;
            const summary = parseCitationCompletedData(parsed.data);
            if (summary === null) break;
            setCitationSummary(summary);
            if (summary.status === "completed") fetchCitations();
            break;
          }
          case "task_completed":
            terminalRef.current = parsed;
            setTerminalEvent(parsed);
            setStatus("success");
            refreshArtifacts();
            break;
          case "task_failed":
            runRef.current += 1;
            terminalRef.current = parsed;
            setTerminalEvent(parsed);
            setStatus("failed");
            setFiles([]);
            setMarkdown(null);
            setMarkdownError(null);
            setCitationSummary(null);
            setCitations(null);
            setCitationsLoading(false);
            setCitationsError(null);
            setLiveDocument(null);
            setLiveLoading(false);
            setLiveError(null);
            setLiveDeliveryStatus("idle");
            setLiveProgress(null);
            break;
          case "task_cancelled":
            runRef.current += 1;
            terminalRef.current = parsed;
            setTerminalEvent(parsed);
            setStatus("cancelled");
            setFiles([]);
            setMarkdown(null);
            setMarkdownError(null);
            setCitationSummary(null);
            setCitations(null);
            setCitationsLoading(false);
            setCitationsError(null);
            setLiveDocument(null);
            setLiveLoading(false);
            setLiveError(null);
            setLiveDeliveryStatus("idle");
            setLiveProgress(null);
            break;
          default:
            break;
        }
      };
    } catch {
      if (cancelled) return;
      setConnectionState("error");
      if (terminalRef.current !== null) return;
      setStatus("connection-error");
      setError(CONNECTION_FAILED_MESSAGE);
    }
    return () => {
      cancelled = true;
      if (socket) {
        socket.onopen = null;
        socket.onclose = null;
        socket.onerror = null;
        socket.onmessage = null;
        try {
          socket.close();
        } catch {
          // Already closed or failed — nothing to do.
        }
      }
    };
  }, [
    apiBaseUrl,
    fetchCitations,
    fetchLiveCitations,
    refreshArtifacts,
    threadId,
  ]);

  const setQuery = useCallback((value: string) => {
    setQueryState(value);
  }, []);

  const selectFile = useCallback((file: File | null) => {
    setSelectedFile(file);
  }, []);

  const upload = useCallback(() => {
    if (selectedFile === null) return;
    const file = selectedFile;
    const currentThreadId = threadId;
    const session = sessionRef.current;
    setStatus("uploading");
    setError(null);
    uploadConstraint(apiBaseUrl, currentThreadId, file)
      .then((response) => {
        if (sessionRef.current !== session) return;
        // Ready only with an accepted backend response entry; the displayed
        // name/size come from that response, never from the local File.
        const accepted = response.files?.[0];
        if (!accepted) {
          setUploadedFile(null);
          setStatus("idle");
          setError(UPLOAD_FAILED_MESSAGE);
          return;
        }
        setUploadedFile({ name: accepted.name, size: accepted.size });
        setStatus("ready");
      })
      .catch((cause: unknown) => {
        if (sessionRef.current !== session) return;
        setUploadedFile(null);
        setStatus("idle");
        setError(stableMessage(cause, UPLOAD_FAILED_MESSAGE));
      });
  }, [apiBaseUrl, selectedFile, threadId]);

  const submit = useCallback(() => {
    if (uploadedFile === null) return;
    const trimmed = query.trim();
    if (trimmed === "") return;
    if (connectionState !== "open") return;
    const currentThreadId = threadId;
    const session = sessionRef.current;
    // A new run clears the previous run's terminal/error/artifact display
    // before submission; the terminal guard resets with it and late artifact
    // responses from the finished run are discarded via the run guard.
    runRef.current += 1;
    terminalRef.current = null;
    setTerminalEvent(null);
    setEvents([]);
    setFiles([]);
    setMarkdown(null);
    setMarkdownError(null);
    setCitationSummary(null);
    setCitations(null);
    setCitationsLoading(false);
    setCitationsError(null);
    setLiveDocument(null);
    setLiveLoading(false);
    setLiveError(null);
    setLiveDeliveryStatus("idle");
    setLiveProgress(null);
    setError(null);
    setStatus("ready");
    // Guard the in-flight POST so a second click cannot duplicate the start;
    // the pending flag never infers a terminal state — task_started owns that.
    setTaskStartPending(true);
    startTask(apiBaseUrl, currentThreadId, trimmed).catch((cause: unknown) => {
      if (sessionRef.current !== session) return;
      // A duplicate/start failure is visible but never infers success.
      setError(stableMessage(cause, "Task start failed."));
    }).finally(() => {
      if (sessionRef.current === session) setTaskStartPending(false);
    });
  }, [apiBaseUrl, connectionState, query, threadId, uploadedFile]);

  const cancel = useCallback(() => {
    if (status !== "running") return;
    const currentThreadId = threadId;
    const session = sessionRef.current;
    cancelTask(apiBaseUrl, currentThreadId).catch((cause: unknown) => {
      if (sessionRef.current !== session) return;
      // 404 stays a visible "no active task" error; the UI becomes
      // cancelled only when the task_cancelled event arrives.
      setError(stableMessage(cause, "Cancellation failed."));
    });
  }, [apiBaseUrl, status, threadId]);

  const newSession = useCallback(() => {
    // A new UUID replaces the old one; the WebSocket effect reconnects and
    // closes the previous socket. Every run field returns to its empty form.
    sessionRef.current += 1;
    runRef.current += 1;
    terminalRef.current = null;
    setTaskStartPending(false);
    setThreadId(createThreadId());
    setQueryState("");
    setSelectedFile(null);
    setUploadedFile(null);
    setStatus("idle");
    setError(null);
    setEvents([]);
    setTerminalEvent(null);
    setFiles([]);
    setMarkdown(null);
    setMarkdownError(null);
    setCitationSummary(null);
    setCitations(null);
    setCitationsLoading(false);
    setCitationsError(null);
    setLiveDocument(null);
    setLiveLoading(false);
    setLiveError(null);
    setLiveDeliveryStatus("idle");
    setLiveProgress(null);
  }, []);

  return {
    threadId,
    health: healthInfo,
    healthError,
    connectionState,
    newSession,
    query,
    setQuery,
    selectedFile,
    selectFile,
    uploadedFile,
    upload,
    submit,
    cancel,
    status,
    error,
    taskStartPending,
    events,
    terminalEvent,
    files,
    markdown,
    markdownError,
    refreshArtifacts,
    citationSummary,
    citations,
    citationsLoading,
    citationsError,
    liveDocument,
    liveLoading,
    liveError,
    liveDeliveryStatus,
    liveProgress,
  };
}
