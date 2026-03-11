import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";

import { fetchAgents, fetchHealth, invokeAi, streamChat } from "../api/client";
import { buildConversationTitleInstructions, buildConversationTitleMessage } from "../lib/aiPrompts";
import {
  agentSupportsOrchestration,
  buildChatTitle,
  createAssistantMessage,
  createChat,
  createThinkingEvent,
  createUserMessage,
  filterTree,
  normalizeAgentTree,
  normalizeRuntimeMode,
  resolveChatRuntimeMode,
  serializeConversationHistory,
} from "../lib/chatWorkspace";
import { sanitizeModelName } from "../lib/preferences";

const EXECUTION_EVENT_TYPES = new Set([
  "thinking_step",
  "tool_selection_reason",
  "tool_started",
  "tool_completed",
  "skill_context_selected",
  "model_started",
  "error",
]);

function buildSessionKey(userId, agentId, runtimeMode, modelName) {
  const normalizedModelName = sanitizeModelName(modelName) || "__default_model__";
  return `${userId}::${agentId}::${normalizeRuntimeMode(runtimeMode)}::${normalizedModelName}`;
}

export function useWorkspaceChat(userId, responseStreaming, modelName) {
  const [tree, setTree] = useState([]);
  const [agents, setAgents] = useState([]);
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState("");
  const [runningChatIds, setRunningChatIds] = useState(() => new Set());
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(true);
  const [agentDirectoryLoading, setAgentDirectoryLoading] = useState(false);
  const [initialLoadError, setInitialLoadError] = useState("");
  const [initialLoadRetrying, setInitialLoadRetrying] = useState(false);
  const [serviceHealth, setServiceHealth] = useState({
    state: "checking",
    message: "Checking the agent service.",
  });
  const [error, setError] = useState("");
  const deferredSearch = useDeferredValue(searchText);
  const loadRequestRef = useRef(0);
  const pendingAssistantTextRef = useRef(new Map());
  const flushAssistantFrameRef = useRef(0);

  const applyAgentCatalog = useCallback((data) => {
    const incomingAgents = data.agents || [];
    setTree(normalizeAgentTree(data.tree || []));
    setAgents(incomingAgents);
    setChats((prev) => prev.map((chat) => {
      const agent = incomingAgents.find((item) => item.id === chat.agentId) || null;
      const nextRuntimeMode = resolveChatRuntimeMode(agent, chat.runtimeMode);
      if (nextRuntimeMode === chat.runtimeMode) {
        return chat;
      }

      return {
        ...chat,
        runtimeMode: nextRuntimeMode,
        updatedAt: Date.now(),
      };
    }));
    return incomingAgents;
  }, []);

  const loadWorkspace = useCallback(async ({ retry = false } = {}) => {
    const requestId = loadRequestRef.current + 1;
    loadRequestRef.current = requestId;

    setLoading(true);
    setError("");
    setInitialLoadRetrying(retry);

    if (!retry) {
      setInitialLoadError("");
      setServiceHealth({
        state: "checking",
        message: "Checking whether the agent service is reachable.",
      });
    } else {
      setServiceHealth((current) => ({
        state: current.state === "up" ? "checking" : "down",
        message: "Retrying connection to the agent service.",
      }));
    }

    const healthPromise = fetchHealth().then((result) => {
      if (loadRequestRef.current !== requestId) {
        return result;
      }

      setServiceHealth({
        state: result.ok ? "up" : "down",
        message: result.ok
          ? "Agent service is responding."
          : result.message || "The agent service may be down or unresponsive.",
      });

      return result;
    });

    try {
      const data = await fetchAgents();
      if (loadRequestRef.current !== requestId) {
        return;
      }

      applyAgentCatalog(data);
      setChats([]);
      setActiveChatId("");
      setInitialLoadError("");
      setInitialLoadRetrying(false);
    } catch (err) {
      const health = await healthPromise;
      if (loadRequestRef.current !== requestId) {
        return;
      }

      const message = err.message || "Failed to load agents.";
      setInitialLoadError(message);
      setInitialLoadRetrying(false);
      setServiceHealth({
        state: health?.ok ? "up" : "down",
        message: health?.ok
          ? "Agent service is reachable, but loading the live agent registry did not complete."
          : health?.message || "The agent service may be down or unresponsive.",
      });
    } finally {
      if (loadRequestRef.current === requestId) {
        setInitialLoadRetrying(false);
        setLoading(false);
      }
    }
  }, [applyAgentCatalog]);

  useEffect(() => {
    void loadWorkspace();

    return () => {
      if (flushAssistantFrameRef.current) {
        window.cancelAnimationFrame(flushAssistantFrameRef.current);
      }
      pendingAssistantTextRef.current.clear();
      loadRequestRef.current += 1;
    };
  }, [loadWorkspace]);

  const activeChat = useMemo(
    () => chats.find((chat) => chat.id === activeChatId) || null,
    [chats, activeChatId],
  );
  const activeAgentId = activeChat?.agentId || "";
  const activeAgent = useMemo(
    () => agents.find((item) => item.id === activeAgentId) || null,
    [agents, activeAgentId],
  );
  const activeRuntimeMode = useMemo(
    () => resolveChatRuntimeMode(activeAgent, activeChat?.runtimeMode || ""),
    [activeAgent, activeChat?.runtimeMode],
  );
  const activeSessionId = activeChat?.sessionIds?.[
    buildSessionKey(userId, activeAgentId, activeRuntimeMode, modelName)
  ] || "";
  const orchestrationAvailable = agentSupportsOrchestration(activeAgent);
  const isSending = activeChat ? runningChatIds.has(activeChat.id) : false;
  const filteredTree = useMemo(
    () => filterTree(tree, deferredSearch),
    [tree, deferredSearch],
  );

  const updateChat = (chatId, updater) => {
    setChats((prev) => prev.map((chat) => (chat.id === chatId ? updater(chat) : chat)));
  };

  const updateMessage = (chatId, messageId, updater) => {
    setChats((prev) =>
      prev.map((chat) => {
        if (chat.id !== chatId) {
          return chat;
        }

        const index = chat.messages.findIndex((item) => item.id === messageId);
        if (index === -1) {
          return chat;
        }

        const messages = [...chat.messages];
        messages[index] = updater(messages[index]);

        return {
          ...chat,
          messages,
          updatedAt: Date.now(),
        };
      }),
    );
  };

  const flushPendingAssistantText = useCallback(() => {
    if (flushAssistantFrameRef.current) {
      window.cancelAnimationFrame(flushAssistantFrameRef.current);
      flushAssistantFrameRef.current = 0;
    }

    const pendingChunks = pendingAssistantTextRef.current;
    if (!pendingChunks.size) {
      return;
    }

    let hasRemainingQueuedText = false;

    setChats((prev) => prev.map((chat) => {
      let messages = null;

      chat.messages.forEach((message, index) => {
        const key = `${chat.id}:${message.id}`;
        const queuedText = pendingChunks.get(key) || "";

        if (!queuedText) {
          return;
        }

        if (!messages) {
          messages = [...chat.messages];
        }

        const nextMessage = {
          ...messages[index],
        };

        if (queuedText) {
          const [revealedText, remainingText] = consumeRevealChunk(queuedText);
          nextMessage.text = `${nextMessage.text}${revealedText}`;
          nextMessage.streaming = true;

          if (remainingText) {
            pendingChunks.set(key, remainingText);
            hasRemainingQueuedText = true;
          } else {
            pendingChunks.delete(key);
          }
        }

        messages[index] = nextMessage;
      });

      if (!messages) {
        return chat;
      }

      return {
        ...chat,
        messages,
        updatedAt: Date.now(),
      };
    }));

    if (hasRemainingQueuedText) {
      scheduleAssistantFlush();
    }
  }, []);

  const scheduleAssistantFlush = useCallback(() => {
    if (flushAssistantFrameRef.current) {
      return;
    }

    flushAssistantFrameRef.current = window.requestAnimationFrame(() => {
      flushAssistantFrameRef.current = 0;
      flushPendingAssistantText();
    });
  }, [flushPendingAssistantText]);

  const appendThinkingEvent = (chatId, messageId, type, payload) => {
    const event = createThinkingEvent(type, payload);
    updateMessage(chatId, messageId, (current) => ({
      ...current,
      thinking: upsertThinkingEvent(current.thinking || [], event),
    }));
  };

  const onSelectAgent = (agentId) => {
    setError("");

    if (!agentId || agentId === activeAgentId) {
      return;
    }

    if (!activeChat) {
      const nextChat = createChat(agentId, agents, chats);
      setChats((prev) => [nextChat, ...prev]);
      setActiveChatId(nextChat.id);
      return;
    }

    updateChat(activeChat.id, (chat) => ({
      ...chat,
      agentId,
      runtimeMode: resolveChatRuntimeMode(
        agents.find((item) => item.id === agentId) || null,
        chat.runtimeMode,
      ),
      title: chat.messages.length ? chat.title : buildChatTitle(agentId, agents, chats, chat.id),
      titleSource: chat.messages.length ? chat.titleSource : "default",
      updatedAt: Date.now(),
    }));
  };

  const onSelectChat = (chatId) => {
    setActiveChatId(chatId);
    setError("");
  };

  const onNewChat = (agentId = activeAgentId || agents[0]?.id || "") => {
    if (!agentId) {
      return;
    }

    const nextChat = createChat(agentId, agents, chats);
    setChats((prev) => [nextChat, ...prev]);
    setActiveChatId(nextChat.id);
    setError("");
  };

  const refreshAgentDirectory = useCallback(async () => {
    setError("");
    setAgentDirectoryLoading(true);

    try {
      const data = await fetchAgents();
      applyAgentCatalog(data);

      return data;
    } catch (err) {
      const health = await fetchHealth();
      const message = health.ok
        ? (err.message || "Failed to refresh agents.")
        : `${err.message || "Failed to refresh agents."} Agent service may be down.`;
      setError(message);
      throw new Error(message);
    } finally {
      setAgentDirectoryLoading(false);
    }
  }, [activeChatId, applyAgentCatalog]);

  const onSetRuntimeMode = (nextMode) => {
    if (!activeChat || !activeAgentId || runningChatIds.has(activeChat.id)) {
      return;
    }

    updateChat(activeChat.id, (chat) => ({
      ...chat,
      runtimeMode: resolveChatRuntimeMode(activeAgent, nextMode),
      updatedAt: Date.now(),
    }));
    setError("");
  };

  const onSend = async (text) => {
    if (!activeChat || !activeAgentId) {
      return;
    }

    const chatId = activeChat.id;
    const runtimeMode = activeRuntimeMode;
    if (runningChatIds.has(chatId)) {
      return;
    }

    const assistantMessage = createAssistantMessage({
      agentId: activeAgentId,
      agentName: activeAgent?.name || activeAgentId,
      runtimeMode,
    });
    const userMessage = createUserMessage(text, {
      targetAgentId: activeAgentId,
      targetAgentName: activeAgent?.name || activeAgentId,
      runtimeMode,
    });

    const shouldGenerateTitle = activeChat.messages.every((item) => item.role !== "user");
    const conversationHistory = serializeConversationHistory(activeChat.messages);
    let finalAssistantText = "";

    updateChat(chatId, (chat) => ({
      ...chat,
      title: chat.title,
      titleSource: shouldGenerateTitle ? "pending" : chat.titleSource,
      messages: [...chat.messages, userMessage, assistantMessage],
      updatedAt: Date.now(),
    }));

    setRunningChatIds((prev) => {
      const next = new Set(prev);
      next.add(chatId);
      return next;
    });
    setError("");

    if (shouldGenerateTitle) {
      void invokeAi({
        agentId: activeAgentId,
        modelName,
        instructions: buildConversationTitleInstructions(),
        message: buildConversationTitleMessage(text),
      }).then((title) => {
        if (!title.trim()) {
          updateChat(chatId, (chat) => ({
            ...chat,
            titleSource: "default",
          }));
          return;
        }

        updateChat(chatId, (chat) => ({
          ...chat,
          title,
          titleSource: "generated",
          updatedAt: Date.now(),
        }));
      }).catch(() => {
        updateChat(chatId, (chat) => ({
          ...chat,
          titleSource: chat.titleSource === "pending" ? "default" : chat.titleSource,
        }));
      });
    }

    try {
      const result = await streamChat({
        agentId: activeAgentId,
        mode: runtimeMode,
        modelName,
        message: text,
        sessionId: activeSessionId || null,
        userId,
        history: conversationHistory,
        stream: responseStreaming,
        onEvent: (type, payload = {}) => {
          if (type === "run_started" && payload.session_id) {
            updateChat(chatId, (chat) => ({
              ...chat,
              sessionIds: {
                ...(chat.sessionIds || {}),
                [buildSessionKey(userId, activeAgentId, runtimeMode, modelName)]: payload.session_id,
              },
              updatedAt: Date.now(),
            }));
          }

          if (type === "thinking_step") {
            appendThinkingEvent(chatId, assistantMessage.id, type, payload);
          }

          if (EXECUTION_EVENT_TYPES.has(type) && type !== "thinking_step") {
            appendThinkingEvent(chatId, assistantMessage.id, type, payload);
          }

          if (type === "run_started") {
            updateMessage(chatId, assistantMessage.id, (current) => ({
              ...current,
              thinkingActive: true,
            }));
          }

          if (type === "assistant_delta" && payload.text) {
            finalAssistantText += payload.text;
            const key = `${chatId}:${assistantMessage.id}`;
            pendingAssistantTextRef.current.set(
              key,
              `${pendingAssistantTextRef.current.get(key) || ""}${payload.text}`,
            );
            scheduleAssistantFlush();
          }

          if (type === "assistant_message") {
            finalAssistantText = payload.text || finalAssistantText;
            const key = `${chatId}:${assistantMessage.id}`;
            pendingAssistantTextRef.current.delete(key);
            flushPendingAssistantText();
            updateMessage(chatId, assistantMessage.id, (current) => ({
              ...current,
              text: payload.text || finalAssistantText || current.text,
              streaming: false,
              usage: payload.usage || current.usage || null,
            }));
          }

          if (type === "run_completed") {
            updateMessage(chatId, assistantMessage.id, (current) => ({
              ...current,
              thinkingActive: false,
            }));
          }

          if (type === "error") {
            const key = `${chatId}:${assistantMessage.id}`;
            pendingAssistantTextRef.current.delete(key);
            flushPendingAssistantText();
            updateMessage(chatId, assistantMessage.id, (current) => ({
              ...current,
              text: current.text || "Run failed before a final assistant message.",
              streaming: false,
              thinkingActive: false,
            }));
          }
        },
      });

      if (result.sessionId) {
        updateChat(chatId, (chat) => ({
          ...chat,
          sessionIds: {
            ...(chat.sessionIds || {}),
            [buildSessionKey(
              userId,
              activeAgentId,
              result.mode || runtimeMode,
              modelName,
            )]: result.sessionId,
          },
          updatedAt: Date.now(),
        }));
      }
    } catch (err) {
      const key = `${chatId}:${assistantMessage.id}`;
      pendingAssistantTextRef.current.delete(key);
      flushPendingAssistantText();
      setError(err.message || "Failed to stream response.");
      updateMessage(chatId, assistantMessage.id, (current) => ({
        ...current,
        text: current.text || "Request failed before streaming began.",
        streaming: false,
        thinking: [
          ...(current.thinking || []),
          createThinkingEvent("thinking_step", {
            label: "Could not complete the answer",
            detail: err.message || "Request failed before streaming began.",
            state: "error",
          }),
        ],
        thinkingActive: false,
      }));
    } finally {
      setRunningChatIds((prev) => {
        const next = new Set(prev);
        next.delete(chatId);
        return next;
      });
    }
  };

  return {
    activeAgent,
    activeAgentId,
    activeRuntimeMode,
    activeSessionId,
    activeChat,
    agents,
    agentDirectoryLoading,
    chats,
    error,
    filteredTree,
    initialLoadError,
    initialLoadRetrying,
    isSending,
    loading,
    onNewChat,
    onSelectAgent,
    onSelectChat,
    onSetRuntimeMode,
    onSend,
    orchestrationAvailable,
    refreshAgentDirectory,
    retryInitialLoad: loadWorkspace,
    searchText,
    serviceHealth,
    setSearchText,
  };
}

function consumeRevealChunk(text, targetLength = 34, maxLength = 72) {
  const value = String(text || "");
  if (!value) {
    return ["", ""];
  }

  if (value.length <= targetLength) {
    return [value, ""];
  }

  const windowEnd = Math.min(value.length, maxLength);
  const remainderWindow = value.slice(targetLength, windowEnd);
  const boundaryMatch = remainderWindow.match(/^\S*\s+/);
  const splitIndex = boundaryMatch
    ? targetLength + boundaryMatch[0].length
    : windowEnd;

  return [value.slice(0, splitIndex), value.slice(splitIndex)];
}

function upsertThinkingEvent(events, nextEvent) {
  if (!nextEvent.stepId) {
    return [...events, nextEvent];
  }

  const index = events.findIndex((event) => event.stepId === nextEvent.stepId);
  if (index === -1) {
    return [...events, nextEvent];
  }

  const updated = [...events];
  const mergedEvent = {
    ...updated[index],
    ...nextEvent,
    id: updated[index].id,
    stepId: updated[index].stepId,
  };
  updated.splice(index, 1);
  updated.push(mergedEvent);
  return updated;
}
