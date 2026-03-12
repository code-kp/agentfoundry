import React from "react";

import { Composer } from "./Composer";
import { MessageList } from "./MessageList";

export function ChatPanel({
  agentId,
  agentName,
  agentDescription,
  chatTitle,
  sessionId,
  messages,
  isSending,
  isRefreshingTitle,
  disabled,
  orchestrationAvailable,
  defaultModelId,
  modelId,
  modelOptions,
  modelsLoading,
  runtimeMode,
  onModelIdChange,
  onOpenAgentPicker,
  onRefreshTitle,
  onSetRuntimeMode,
  onSend,
}) {
  const hasActiveAgent = Boolean(agentName || agentId);
  const canRefreshTitle = hasActiveAgent && messages.some((message) => (
    ["user", "assistant"].includes(message?.role)
      && String(message?.text || "").trim()
  ));
  const sessionLabel = sessionId ? "Saved context" : "Fresh context";
  const title = hasActiveAgent
    ? chatTitle || "New conversation"
    : "Start a conversation";

  return (
    <section className="workspace-stage card-shell">
      <header className="workspace-header">
        <div className="workspace-header-copy">
          <div className="workspace-title-row">
            <div className="workspace-title-heading">
              <h1>{title}</h1>
              {hasActiveAgent ? (
                <button
                  type="button"
                  className={isRefreshingTitle ? "workspace-title-refresh refreshing" : "workspace-title-refresh"}
                  onClick={onRefreshTitle}
                  disabled={!canRefreshTitle || isSending || isRefreshingTitle}
                  aria-label="Refresh conversation title"
                  title="Regenerate the title from the conversation summary"
                >
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <path
                      d="M13.65 3.35A6 6 0 1 0 14 9h-1.8a4.25 4.25 0 1 1-1.04-4.45L9.5 6.2H14V1.7l-1.35 1.65Z"
                      fill="currentColor"
                    />
                  </svg>
                </button>
              ) : null}
            </div>
            {hasActiveAgent ? (
              <div className="workspace-meta">
                <span>{isSending ? "Streaming" : "Ready"}</span>
                <span>{sessionLabel}</span>
              </div>
            ) : (
              <div className="workspace-meta">
                <span>Choose an agent to begin</span>
              </div>
            )}
          </div>
          <div className="workspace-agent-inline">
            <span className="workspace-agent-label">Agent</span>
            <strong>{agentName || agentId || "Choose agent"}</strong>
            <button
              type="button"
              className="agent-edit-button"
              disabled={isSending}
              onClick={onOpenAgentPicker}
            >
              {hasActiveAgent ? "Edit" : "Choose"}
            </button>
          </div>
          {agentDescription ? <p className="workspace-agent-description">{agentDescription}</p> : null}
        </div>
      </header>
      <div className="transcript-shell">
        <MessageList
          messages={messages}
          agentName={agentName || agentId}
          agentDescription={agentDescription}
        />
        <footer className="composer-shell">
          <Composer
            disabled={disabled}
            isSending={isSending}
            hasAgent={Boolean(agentName || agentId)}
            agentName={agentName || agentId}
            orchestrationAvailable={orchestrationAvailable}
            defaultModelId={defaultModelId}
            modelId={modelId}
            modelOptions={modelOptions}
            modelsLoading={modelsLoading}
            runtimeMode={runtimeMode}
            onModelIdChange={onModelIdChange}
            onSetRuntimeMode={onSetRuntimeMode}
            onSend={onSend}
          />
        </footer>
      </div>
    </section>
  );
}
