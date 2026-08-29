export type UserRole = "admin" | "user";
export type SourceKind = "knowledge" | "session_file" | "web";
export type TurnStatus = "pending" | "running" | "completed" | "failed";

export interface User {
  id: string;
  username: string;
  role: UserRole;
}

export interface AdminUserSummary extends User {
  conversation_count: number;
}

export interface Attachment {
  id: string;
  name: string;
  size: number;
  media_type: string;
  active: boolean;
}

export interface EvidenceItem {
  evidence_id: string;
  source_kind: SourceKind;
  title: string;
  locator_kind: "url" | "chunk" | "file";
  locator_value: string;
  quote: string;
  hostname: string | null;
  published_at: string | null;
}

export interface Claim {
  claim_id: string;
  statement: string;
  evidence_ids: string[];
}

export interface TurnResult {
  schema_version: "5.0.0";
  answer: string;
  claims: Claim[];
  evidence: EvidenceItem[];
  limitations: string[];
}

export interface Turn {
  id: string;
  question: string;
  answer: string | null;
  use_web: boolean;
  status: TurnStatus;
  attachment_ids: string[];
  result: TurnResult | null;
  created_at: string;
  completed_at: string | null;
}

export interface Conversation {
  id: string;
  owner_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  attachments: Attachment[];
  turns: Turn[];
}

/** 轻量会话元数据（G10 lite 端点）：不含回合与附件。 */
export type ConversationSummary = Omit<Conversation, "turns" | "attachments">;

export type ConversationEventType =
  | "turn.started"
  | "stage.changed"
  | "answer.delta"
  | "evidence.ready"
  | "report.updated"
  | "turn.completed"
  | "turn.failed"
  | "turn.cancelled";

export interface ConversationEvent {
  schema_version: "5.0.0";
  sequence: number;
  conversation_id: string;
  turn_id: string;
  type: ConversationEventType;
  stage: string | null;
  message: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface LibraryDocument {
  document_id: string;
  name: string;
  chunks: number;
}
