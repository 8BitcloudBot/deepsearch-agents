import { useRef, useState } from "react";
import type { AdminUserSummary, Conversation, EvidenceItem, Turn } from "./contracts";

export interface ConversationWorkspaceState {
  user: { id: string; username: string; role: "admin" | "user" } | null;
  conversations: Conversation[];
  adminUsers: AdminUserSummary[];
  activeConversationId: string | null;
  question: string;
  useWeb: boolean;
  stage: string | null;
  error: string | null;
  setQuestion: (value: string) => void;
  setUseWeb: (value: boolean) => void;
  selectConversation: (id: string) => void;
  createConversation: () => void | Promise<void>;
  deleteConversation: (id: string) => void | Promise<void>;
  renameConversation: (id: string, title: string) => void | Promise<void>;
  resetUserData: (id: string) => void | Promise<void>;
  submitTurn: () => void | Promise<void>;
  view: "research" | "library";
  setView: (view: "research" | "library") => void;
  libraryDocs: { document_id: string; name: string; chunks: number }[];
  libraryBusy: boolean;
  uploadLibraryDocuments: (files: File[]) => void | Promise<void>;
  deleteLibraryDocument: (id: string) => void | Promise<void>;
  logout: () => void | Promise<void>;
  reportUrl: (id: string) => string;
}

const sourceLabels: Record<EvidenceItem["source_kind"], string> = {
  knowledge: "本地知识库",
  session_file: "会话文件",
  web: "实时网络",
};

function EvidenceCard({ evidence, anchorId }: { evidence: EvidenceItem; anchorId: string }) {
  const isLink = evidence.locator_kind === "url";
  const [expanded, setExpanded] = useState(false);
  return (
    <article className="evidence-card" id={anchorId}>
      <div className="evidence-card-topline">
        <span className={`evidence-kind evidence-kind-${evidence.source_kind}`}>
          {sourceLabels[evidence.source_kind]}
        </span>
        {evidence.hostname && <span className="evidence-hostname">{evidence.hostname}</span>}
      </div>
      <strong>{evidence.title}</strong>
      <blockquote className={expanded ? "" : "evidence-quote-clamped"}>{evidence.quote}</blockquote>
      <button
        className="evidence-expand"
        type="button"
        aria-label={expanded ? "收起证据原文" : "展开证据原文"}
        onClick={() => setExpanded((value) => !value)}
      >{expanded ? "收起" : "展开"}</button>
      <div className="evidence-location">
        {isLink ? (
          <a href={evidence.locator_value} target="_blank" rel="noreferrer">打开来源</a>
        ) : evidence.locator_value}
        {evidence.published_at && <time dateTime={evidence.published_at}>{evidence.published_at.slice(0, 10)}</time>}
      </div>
    </article>
  );
}

function TurnMessage({ turn }: { turn: Turn }) {
  const result = turn.result;
  const evidenceById = new Map((result?.evidence ?? []).map((item) => [item.evidence_id, item]));
  const citedIds = new Set((result?.claims ?? []).flatMap((claim) => claim.evidence_ids));
  const citedEvidence = (result?.evidence ?? []).filter((item) => citedIds.has(item.evidence_id));
  const renderAnswer = (paragraph: string) => paragraph.split(/(\[\d+\])/).map((part, index) => {
    const match = /^\[(\d+)\]$/.exec(part);
    const evidenceNumber = match ? Number(match[1]) : 0;
    const evidence = result?.evidence[evidenceNumber - 1];
    return evidence ? (
      <a
        className="citation-marker"
        href={`#turn-${turn.id}-evidence-${evidence.evidence_id}`}
        aria-label={`查看依据 ${evidenceNumber}`}
        key={`${part}-${index}`}
      >{part}</a>
    ) : part;
  });
  return (
    <article className={`turn-message turn-${turn.status}`}>
      <div className="message-question"><span className="message-label">你</span><p>{turn.question}</p></div>
      {turn.status === "failed" ? (
        <div className="message-error">本轮没有生成可交付回答，请调整问题后重试。</div>
      ) : (
        <>
          {result && result.limitations.length > 0 && (
            <div className="turn-limitations"><strong>本轮限制</strong><ul>{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
          )}
          <div className="message-answer"><span className="message-label">助手</span>
            <div className="answer-body">
              {(turn.answer ?? result?.answer ?? "正在整理回答…").split(/\n{2,}/).map((paragraph, index) => (
                <p key={`${turn.id}-paragraph-${index}`}>{renderAnswer(paragraph)}</p>
              ))}
            </div>
          </div>
          {result && (
            <section className="turn-evidence" aria-label="本轮依据">
              <h3>本轮依据</h3>
              {result.claims.length > 0 ? result.claims.map((claim) => (
                <div className="claim-block" id={`turn-${turn.id}-${claim.claim_id}`} key={claim.claim_id}>
                  <p className="claim-statement">{claim.statement}</p>
                  <div className="claim-citations" aria-label="声明引用">
                    {claim.evidence_ids.map((id) => {
                      const evidence = evidenceById.get(id);
                      const number = result.evidence.findIndex((item) => item.evidence_id === id) + 1;
                      return evidence && number > 0 ? (
                        <a key={id} href={`#turn-${turn.id}-evidence-${id}`} aria-label={`查看证据 ${number}`}>[{number}]</a>
                      ) : null;
                    })}
                  </div>
                </div>
              )) : <p className="muted">本轮没有需要引用的事实声明。</p>}
              {citedEvidence.length > 0 && (
                <div className="turn-evidence-list">
                  {citedEvidence.map((item) => (
                    <EvidenceCard
                      key={item.evidence_id}
                      evidence={item}
                      anchorId={`turn-${turn.id}-evidence-${item.evidence_id}`}
                    />
                  ))}
                </div>
              )}
            </section>
          )}
        </>
      )}
    </article>
  );
}

function Sidebar({ state, active }: { state: ConversationWorkspaceState; active: Conversation | null }) {
  return (
    <aside className="conversation-sidebar">
      <div className="sidebar-heading">
        <div><span className="section-kicker">DEEPSEARCH</span><h1>研究助手</h1></div>
        <button className="icon-button" type="button" aria-label="新建会话" title="新建会话" onClick={() => void state.createConversation()}>+</button>
      </div>
      <div className="sidebar-user"><span className="connection-dot connection-open" />{state.user?.username}<button type="button" onClick={() => void state.logout()}>退出</button></div>
      <div className="library-nav" role="tablist" aria-label="工作区视图">
        <button type="button" className={state.view === "research" ? "active" : ""} onClick={() => state.setView("research")}>研究</button>
        <button type="button" className={state.view === "library" ? "active" : ""} onClick={() => state.setView("library")}>知识库</button>
      </div>
      <nav className="conversation-list" aria-label="会话列表">
        {state.conversations.map((item) => (
          <div className={`conversation-item ${item.id === active?.id ? "conversation-item-active" : ""}`} key={item.id}>
            <button type="button" onClick={() => state.selectConversation(item.id)}>{item.title}</button>
            <button className="icon-button subtle" type="button" aria-label={`删除${item.title}`} title="删除会话" onClick={() => {
              if (window.confirm("确定删除这个会话吗？")) void state.deleteConversation(item.id);
            }}>×</button>
          </div>
        ))}
        {state.conversations.length === 0 && <p className="sidebar-empty">创建一个会话，开始你的研究。</p>}
      </nav>
      {state.user?.role === "admin" && (
        <section className="admin-data" aria-label="数据管理">
          <h2>数据管理</h2>
          {state.adminUsers.map((item) => (
            <div className="admin-user-row" key={item.id}>
              <div><strong>{item.username}</strong><span>{item.conversation_count} 个会话</span></div>
              {item.id !== state.user?.id && (
                <button type="button" aria-label={`清理 ${item.username} 的数据`} onClick={() => {
                  if (window.confirm(`确定清理 ${item.username} 的全部会话数据吗？`)) void state.resetUserData(item.id);
                }}>清理</button>
              )}
            </div>
          ))}
        </section>
      )}
    </aside>
  );
}

function LibraryPage({ state }: { state: ConversationWorkspaceState }) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <section className="library-page" aria-label="个人知识库">
      <header className="library-header">
        <span className="section-kicker">PERSONAL KNOWLEDGE</span>
        <h2>个人知识库</h2>
        <p>上传 PDF / Markdown / Word / Excel 文档，入库后会在后续研究回合中作为知识来源参与检索。</p>
      </header>
      <div className="library-actions">
        <button className="attachment-add" type="button" disabled={state.libraryBusy} onClick={() => inputRef.current?.click()}>
          {state.libraryBusy ? "正在入库…" : "+ 上传文档"}
        </button>
        <input ref={inputRef} className="visually-hidden" type="file" multiple accept=".txt,.md,.pdf,.docx,.xlsx" onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = "";
          void state.uploadLibraryDocuments(files);
        }} />
      </div>
      <div className="library-list">
        {state.libraryDocs.length === 0 && <p className="sidebar-empty">还没有入库文档。上传后即可被所有后续提问引用。</p>}
        {state.libraryDocs.map((doc) => (
          <div className="library-row" key={doc.document_id}>
            <strong>{doc.name}</strong>
            <small>{doc.chunks} 个分段</small>
            <button type="button" aria-label={`删除${doc.name}`} onClick={() => {
              if (window.confirm(`确定删除 ${doc.name} 吗？`)) void state.deleteLibraryDocument(doc.document_id);
            }}>×</button>
          </div>
        ))}
      </div>
    </section>
  );
}

export function ConversationWorkspace({ state }: { state: ConversationWorkspaceState }) {
  const active = state.conversations.find((item) => item.id === state.activeConversationId) ?? null;
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  return (
    <main className="conversation-shell">
      <Sidebar state={state} active={active} />
      {state.view === "library" ? <LibraryPage state={state} /> : (
      <section className="conversation-main">
        <header className="conversation-header">
          <div className="conversation-title"><span className="section-kicker">MULTI-TURN RESEARCH</span>
            {editingTitle && active ? (
              <form onSubmit={(event) => {
                event.preventDefault();
                if (titleDraft.trim()) void state.renameConversation(active.id, titleDraft.trim());
                setEditingTitle(false);
              }}>
                <input aria-label="会话标题" value={titleDraft} onChange={(event) => setTitleDraft(event.target.value)} maxLength={120} autoFocus />
                <button type="submit" aria-label="保存标题">保存</button>
                <button type="button" onClick={() => setEditingTitle(false)}>取消</button>
              </form>
            ) : <div className="title-row"><h2>{active?.title ?? "开始一项研究"}</h2>{active && <button type="button" className="title-edit" aria-label="重命名会话" onClick={() => { setTitleDraft(active.title); setEditingTitle(true); }}>重命名</button>}</div>}
          </div>
          {active && <a className="report-link" href={state.reportUrl(active.id)} download>下载研究报告</a>}
        </header>
        {state.error && <div role="alert" className="notice notice-error">{state.error}</div>}
        <div className="message-stream">
          {!active ? <div className="empty-conversation"><h3>从一个问题开始</h3><p>本地知识库始终参与；需要最新资料时再打开实时网络。</p></div> : active.turns.length === 0 ? <div className="empty-conversation"><h3>这是一段新的研究</h3><p>试着问一个你正在学习的技术问题。</p></div> : active.turns.map((turn) => <TurnMessage key={turn.id} turn={turn} />)}
        </div>
        <div className="composer-dock">
          {state.stage && <div className="stage-line" role="status"><span className="stage-pulse" />{state.stage}</div>}
          <div className="composer-row">
            <textarea aria-label="研究问题" value={state.question} onChange={(event) => state.setQuestion(event.target.value)} onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void state.submitTurn(); }
            }} placeholder="输入你的研究问题…" />
            <div className="composer-actions">
              <label className="web-toggle"><input type="checkbox" aria-label="使用实时网络" checked={state.useWeb} onChange={(event) => state.setUseWeb(event.target.checked)} /><span>使用实时网络</span></label>
              <button className="send-button" type="button" disabled={!active || !state.question.trim() || Boolean(state.stage)} onClick={() => void state.submitTurn()}>发送</button>
            </div>
          </div>
        </div>
      </section>
      )}
    </main>
  );
}

export function LoginScreen({ onLogin, error }: { onLogin: (username: string, password: string) => Promise<void>; error: string | null }) {
  const [username, setUsername] = useState("user");
  const [password, setPassword] = useState("");
  return <main className="login-shell"><form className="login-panel" onSubmit={(event) => { event.preventDefault(); void onLogin(username, password); }}>
    <span className="section-kicker">DEEPSEARCH</span><h1>研究助手</h1><p>面向 AI 应用开发与大模型研究的多轮对话。</p>
    <label>用户名<input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" /></label>
    <label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" /></label>
    {error && <div role="alert" className="notice notice-error">{error}</div>}
    <button className="send-button" type="submit">登录</button>
  </form></main>;
}
