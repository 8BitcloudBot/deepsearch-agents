import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  FileText,
  Rocket,
  Wrench,
  XCircle,
} from "lucide-react";
import type { JsonValue, TutorialEvent } from "../types";

interface EventFeedProps {
  events: TutorialEvent[];
}

function eventIcon(type: TutorialEvent["type"]) {
  switch (type) {
    case "task_started":
      return <Rocket size={15} aria-hidden="true" />;
    case "agent_started":
    case "agent_completed":
      return <Bot size={15} aria-hidden="true" />;
    case "tool_started":
    case "tool_completed":
      return <Wrench size={15} aria-hidden="true" />;
    case "artifact_created":
      return <FileText size={15} aria-hidden="true" />;
    case "task_completed":
      return <CheckCircle2 size={15} aria-hidden="true" />;
    case "task_cancelled":
      return <XCircle size={15} aria-hidden="true" />;
    case "task_failed":
      return <AlertTriangle size={15} aria-hidden="true" />;
  }
}

function detailText(value: JsonValue): string {
  if (value === null) return "null";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** Data keys surfaced as event details; duplicate values are collapsed. */
const DETAIL_KEYS = [
  "agent_name",
  "tool_name",
  "path",
  "name",
  "media_type",
  "query",
  "status",
  "error",
];

export function EventFeed({ events }: EventFeedProps) {
  return (
    <section aria-label="Event feed" className="feed">
      <h2 className="panel-title">Event Feed</h2>
      {events.length === 0 ? (
        <p className="feed-empty">No events yet — run a task to see progress.</p>
      ) : (
        <ol className="feed-list" aria-label="Tutorial events">
          {events.map((event) => {
            const seen = new Set<string>();
            const details = Object.entries(event.data)
              .filter(([key]) => DETAIL_KEYS.includes(key))
              .filter(([, value]) => {
                const text = detailText(value);
                if (seen.has(text)) return false;
                seen.add(text);
                return true;
              });
            return (
              <li
                key={event.sequence}
                className={`event-item event-${event.type}`}
              >
                <span className="event-icon">{eventIcon(event.type)}</span>
                <div className="event-body">
                  <span className="event-message">{event.message}</span>
                  {details.length > 0 && (
                    <span className="event-details">
                      {details.map(([key, value]) => (
                        <span key={key} className="event-detail">
                          {key}: {detailText(value)}
                        </span>
                      ))}
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
