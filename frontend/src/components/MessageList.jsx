import React, { useCallback, useEffect, useRef, useState } from "react";

import { MessageItem } from "./MessageItem";

const BOTTOM_THRESHOLD_PX = 32;

function scrollContainerToBottom(container, behavior = "smooth") {
  container.scrollTo({
    top: container.scrollHeight,
    behavior,
  });
}

function isScrolledToBottom(container) {
  if (!container) {
    return true;
  }

  const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
  return distanceFromBottom <= BOTTOM_THRESHOLD_PX;
}

export function MessageList({ messages, agentName, agentDescription }) {
  const listRef = useRef(null);
  const [showScrollToLatest, setShowScrollToLatest] = useState(false);
  const followLatestRef = useRef(true);
  const previousMessageCountRef = useRef(messages.length);

  const syncScrollState = useCallback(() => {
    const pinnedToBottom = isScrolledToBottom(listRef.current);
    followLatestRef.current = pinnedToBottom;
    setShowScrollToLatest(!pinnedToBottom);
  }, []);

  useEffect(() => {
    if (!listRef.current) {
      return undefined;
    }

    const nextBehavior = previousMessageCountRef.current < messages.length ? "smooth" : "auto";
    const frameId = window.requestAnimationFrame(() => {
      if (followLatestRef.current && listRef.current) {
        scrollContainerToBottom(listRef.current, nextBehavior);
      }

      syncScrollState();
      previousMessageCountRef.current = messages.length;
    });

    return () => {
      window.cancelAnimationFrame(frameId);
    };
  }, [messages, syncScrollState]);

  if (!messages.length) {
    return (
      <div className="conversation-empty">
        <span className="conversation-empty-badge">{agentName ? "Ready" : "Idle"}</span>
        <h3>{agentName ? `Start with ${agentName}` : "Select an agent to begin"}</h3>
        <p>
          {agentDescription
            || "Switch agents without leaving the thread. Progress updates and responses stay in one shared conversation."}
        </p>
      </div>
    );
  }

  return (
    <div className="message-list-shell">
      <div className="message-list" ref={listRef} onScroll={syncScrollState}>
        {messages.map((message) => <MessageItem key={message.id} message={message} />)}
      </div>
      {showScrollToLatest ? (
        <button
          type="button"
          className="scroll-latest-button"
          onClick={() => {
            if (!listRef.current) {
              return;
            }
            followLatestRef.current = true;
            setShowScrollToLatest(false);
            scrollContainerToBottom(listRef.current, "smooth");
          }}
        >
          <span>Scroll to latest</span>
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path
              d="M3.47 6.97a.75.75 0 0 1 1.06 0L8 10.44l3.47-3.47a.75.75 0 1 1 1.06 1.06l-4 4a.75.75 0 0 1-1.06 0l-4-4a.75.75 0 0 1 0-1.06Z"
              fill="currentColor"
            />
          </svg>
        </button>
      ) : null}
    </div>
  );
}
