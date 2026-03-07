import React, { useEffect, useRef } from "react";

import { MessageItem } from "./MessageItem";

export function MessageList({ messages, agentName, agentDescription }) {
  const listRef = useRef(null);
  const previousSnapshotRef = useRef({
    count: messages.length,
    lastId: messages[messages.length - 1]?.id || null,
    lastText: messages[messages.length - 1]?.text || "",
    lastStreaming: Boolean(messages[messages.length - 1]?.streaming),
  });

  useEffect(() => {
    if (!listRef.current) {
      return;
    }

    const lastMessage = messages[messages.length - 1] || null;
    const snapshot = {
      count: messages.length,
      lastId: lastMessage?.id || null,
      lastText: lastMessage?.text || "",
      lastStreaming: Boolean(lastMessage?.streaming),
    };
    const previousSnapshot = previousSnapshotRef.current;
    const shouldScroll =
      snapshot.count !== previousSnapshot.count
      || snapshot.lastId !== previousSnapshot.lastId
      || (
        snapshot.lastStreaming
        && snapshot.lastText !== previousSnapshot.lastText
      );

    if (shouldScroll) {
      listRef.current.scrollTo({
        top: listRef.current.scrollHeight,
        behavior: snapshot.count === previousSnapshot.count ? "smooth" : "auto",
      });
    }

    previousSnapshotRef.current = snapshot;
  }, [messages]);

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
    <div className="message-list" ref={listRef}>
      {messages.map((message) => <MessageItem key={message.id} message={message} />)}
    </div>
  );
}
