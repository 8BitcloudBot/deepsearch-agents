import {
  AlertCircle,
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
} from "lucide-react";
import type { SessionStatus } from "../types";

interface RunStatusProps {
  status: SessionStatus;
  error: string | null;
}

const STATUS_LABEL: Record<SessionStatus, string> = {
  idle: "Idle",
  connecting: "Connecting",
  running: "Running",
  completed: "Completed",
  cancelled: "Cancelled",
  failed: "Failed",
  error: "Error",
};

export function RunStatus({ status, error }: RunStatusProps) {
  return (
    <section aria-label="Run status" className="run-status">
      <span className={`status-badge status-${status}`}>
        {status === "running" || status === "connecting" ? (
          <Loader2 size={13} className="spin" aria-hidden="true" />
        ) : status === "completed" ? (
          <CheckCircle2 size={13} aria-hidden="true" />
        ) : status === "failed" || status === "error" ? (
          <XCircle size={13} aria-hidden="true" />
        ) : status === "cancelled" ? (
          <AlertCircle size={13} aria-hidden="true" />
        ) : (
          <Circle size={13} aria-hidden="true" />
        )}
        {STATUS_LABEL[status]}
      </span>
      {error && <p className="status-error">{error}</p>}
    </section>
  );
}
