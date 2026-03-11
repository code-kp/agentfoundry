import React, { useEffect, useRef, useState } from "react";
import { formatTime, toDateTimeAttr } from "../lib/time";

function ensureSentence(text) {
  const cleaned = String(text || "").replace(/\s+/g, " ").trim();
  if (!cleaned) {
    return "";
  }
  return /[.!?]$/.test(cleaned) ? cleaned : `${cleaned}.`;
}

function lowerFirst(text) {
  const value = String(text || "").trim();
  if (!value) {
    return "";
  }
  return `${value.charAt(0).toLowerCase()}${value.slice(1)}`;
}

function normalizeText(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}

function narrationFromLabel(label) {
  const clean = String(label || "").trim();
  if (!clean) {
    return "";
  }
  if (/ing$/i.test(clean)) {
    return ensureSentence(`I'm ${lowerFirst(clean)}`);
  }
  if (/ready$/i.test(clean)) {
    const stem = clean.replace(/\s+ready$/i, "").trim();
    return stem ? `I have ${lowerFirst(stem)} ready.` : "I have it ready.";
  }
  if (/completed$/i.test(clean)) {
    const stem = clean.replace(/\s+completed$/i, "").trim();
    return stem ? `I completed ${lowerFirst(stem)}.` : "I completed that step.";
  }
  if (/verified$/i.test(clean)) {
    const stem = clean.replace(/\s+verified$/i, "").trim();
    return stem ? `I verified ${lowerFirst(stem)}.` : "I verified the result.";
  }
  if (/finalized$/i.test(clean)) {
    const stem = clean.replace(/\s+finalized$/i, "").trim();
    return stem ? `I finalized ${lowerFirst(stem)}.` : "I finalized the answer.";
  }
  return ensureSentence(clean);
}

function humanizeName(value, fallback) {
  const cleaned = String(value || "").replace(/_/g, " ").trim();
  return cleaned || fallback;
}

function formatSourceList(chunks) {
  const uniqueSources = [...new Set((chunks || []).map((chunk) => chunk?.source).filter(Boolean))];
  if (!uniqueSources.length) {
    return "the workspace";
  }
  if (uniqueSources.length === 1) {
    return uniqueSources[0];
  }
  if (uniqueSources.length === 2) {
    return `${uniqueSources[0]} and ${uniqueSources[1]}`;
  }
  return `${uniqueSources.slice(0, 2).join(", ")}, and ${uniqueSources.length - 2} more sources`;
}

function summarizeArgs(args) {
  if (!args || typeof args !== "object" || Array.isArray(args)) {
    return "";
  }

  const pairs = Object.entries(args)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .slice(0, 2)
    .map(([key, value]) => {
      const rendered = typeof value === "string" ? `"${value}"` : JSON.stringify(value);
      return `${humanizeName(key, key)}=${rendered}`;
    });

  return pairs.join(", ");
}

function summarizeResponse(response) {
  if (!response) {
    return "";
  }
  if (Array.isArray(response)) {
    return `I got ${response.length} item${response.length === 1 ? "" : "s"} back.`;
  }
  if (typeof response !== "object") {
    return ensureSentence(response);
  }
  if (Array.isArray(response.results)) {
    return `I found ${response.results.length} result${response.results.length === 1 ? "" : "s"}.`;
  }
  if (Array.isArray(response.skills)) {
    return `I found ${response.skills.length} skill file${response.skills.length === 1 ? "" : "s"}.`;
  }
  if (typeof response.content === "string") {
    return "I loaded the requested file.";
  }

  const keys = Object.keys(response).slice(0, 2);
  if (!keys.length) {
    return "";
  }

  const summary = keys.map((key) => `${humanizeName(key, key)}=${JSON.stringify(response[key])}`).join(", ");
  return ensureSentence(summary);
}

function getThinkingNarration(event) {
  if (!event) {
    return "I'm getting started.";
  }

  const data = event.data || {};
  const detail = ensureSentence(event.detail || "");

  if (event.source === "model") {
    return ensureSentence(event.detail || event.body || "I'm thinking through the request.");
  }

  switch (event.type) {
    case "thinking_step":
      switch (event.stepId) {
        case "understand_request":
          return detail || "I'm pinning down what you need before I commit to an approach.";
        case "conversation_context":
          return detail || "I'm checking the recent conversation so this answer stays grounded.";
        case "conversation_memory":
          return detail || "I'm pulling forward the earlier facts and decisions that still matter.";
        case "guidance":
          return detail || "I'm grounding the answer with the relevant saved guidance.";
        case "planning":
          return detail || "I'm deciding on the most reliable way to tackle this.";
        case "answer":
          if (event.state === "done") {
            return detail || "I have the answer ready.";
          }
          if (event.state === "error") {
            return detail || "I couldn't finish the answer cleanly.";
          }
          return detail || "I'm working through the answer now.";
        default: {
          const labelNarration = narrationFromLabel(event.label);
          if (labelNarration) {
            return `${labelNarration}${detail ? ` ${detail}` : ""}`.trim();
          }
          return detail || "I'm working through the request.";
        }
      }
    case "tool_selection_reason": {
      const toolName = humanizeName(data.tool_name, "the next tool");
      const reason = normalizeText(data.reason || event.detail || event.body || "");
      if (!reason) {
        return `I'm going to use ${toolName} for the next step.`;
      }
      return `I'm going to use ${toolName} because ${lowerFirst(reason).replace(/[.!?]+$/, "")}.`;
    }
    case "tool_started": {
      const toolName = humanizeName(data.tool_name, "a tool");
      const argsSummary = summarizeArgs(data.args);
      return argsSummary
        ? `I'm running ${toolName} with ${argsSummary}.`
        : `I'm running ${toolName}.`;
    }
    case "tool_completed": {
      const toolName = humanizeName(data.tool_name, "that tool");
      const responseSummary = summarizeResponse(data.response);
      return responseSummary
        ? `I finished ${toolName}. ${responseSummary}`
        : `I finished ${toolName}.`;
    }
    case "skill_context_selected": {
      const chunks = Array.isArray(data.chunks) ? data.chunks : [];
      if (!chunks.length) {
        return "I'm answering from the current context without pulling in extra workspace guidance.";
      }
      return `I'm pulling in relevant workspace guidance from ${formatSourceList(chunks)} so the answer stays grounded.`;
    }
    case "model_started":
      return `I'm sending this to ${data.model || "the model"} now.`;
    case "error":
      return ensureSentence(data.message || event.body || "I couldn't finish this run.");
    default:
      return ensureSentence(event.body || event.label || "I'm still working through the request.");
  }
}

function getEventKicker(event) {
  if (!event) {
    return "Thinking";
  }
  if (event.source === "model") {
    return "Model thought";
  }
  switch (event.type) {
    case "thinking_step":
      return "Thinking";
    case "tool_selection_reason":
      return "Why this step";
    case "tool_started":
      return "Running a tool";
    case "tool_completed":
      return "Tool result";
    case "skill_context_selected":
      return "Context";
    case "model_started":
      return "Model";
    case "error":
      return "Issue";
    default:
      return "Update";
  }
}

function getSupportingDetail(event, narration, expanded) {
  if (!expanded || !event || event.source === "model") {
    return "";
  }

  const body = normalizeText(event.body || "");
  const narrationText = normalizeText(narration);
  if (!body || body === narrationText) {
    return "";
  }
  return event.body || "";
}

function visibleHistoryEvents(events, expanded, active) {
  const history = events.slice(0, -1);
  if (!history.length) {
    return history;
  }
  if (expanded) {
    return history;
  }
  if (active) {
    return [];
  }
  return history.slice(-3);
}

export function ExecutionSteps({ events, active }) {
  const [expanded, setExpanded] = useState(false);
  const [isSettling, setIsSettling] = useState(false);
  const [isCollapsing, setIsCollapsing] = useState(false);
  const historyRef = useRef(null);
  const collapseStartTimeoutRef = useRef(null);
  const collapseEndTimeoutRef = useRef(null);
  const previousActiveRef = useRef(active);
  const previousEventCountRef = useRef(events.length);
  const latestEvent = events[events.length - 1] || null;
  const latestNarration = getThinkingNarration(latestEvent);
  const latestSupportingDetail = getSupportingDetail(latestEvent, latestNarration, expanded);
  const historyEvents = visibleHistoryEvents(events, expanded, active);
  const hiddenCount = Math.max(events.length - 1 - historyEvents.length, 0);
  const showPanel = active || expanded || isSettling || isCollapsing;
  const showFocusedLayout = active || isSettling || isCollapsing;
  const showCollapsedSummary = !active && !expanded && !isSettling && !isCollapsing && events.length > 0;
  const heading = active ? "Thinking through the request" : "Thought process";
  const summary = latestNarration || (active
    ? "I'm getting oriented before I answer."
    : "The response is complete.");

  const clearCollapseTimers = () => {
    window.clearTimeout(collapseStartTimeoutRef.current);
    window.clearTimeout(collapseEndTimeoutRef.current);
  };

  const beginCollapseAnimation = () => {
    setIsSettling(false);
    setIsCollapsing(true);
    collapseEndTimeoutRef.current = window.setTimeout(() => {
      setIsCollapsing(false);
    }, 420);
  };

  const scheduleCollapse = (delay = 0) => {
    clearCollapseTimers();
    setExpanded(false);

    if (delay > 0) {
      setIsSettling(true);
      collapseStartTimeoutRef.current = window.setTimeout(() => {
        beginCollapseAnimation();
      }, delay);
      return;
    }

    setIsSettling(false);
    beginCollapseAnimation();
  };

  useEffect(() => {
    if (latestEvent?.state === "error" || latestEvent?.type === "error") {
      clearCollapseTimers();
      setIsSettling(false);
      setIsCollapsing(false);
      setExpanded(true);
    }
  }, [latestEvent]);

  useEffect(() => {
    if (!historyRef.current || !historyEvents.length) {
      previousEventCountRef.current = events.length;
      return;
    }

    const behavior = showFocusedLayout && previousEventCountRef.current > 0 ? "smooth" : "auto";
    historyRef.current.scrollTo({
      top: historyRef.current.scrollHeight,
      behavior,
    });
    previousEventCountRef.current = events.length;
  }, [events.length, historyEvents.length, latestNarration, showFocusedLayout]);

  useEffect(() => {
    if (active) {
      clearCollapseTimers();
      setIsSettling(false);
      setIsCollapsing(false);
    } else if (previousActiveRef.current && !expanded) {
      scheduleCollapse(events.length ? 760 : 0);
    }

    previousActiveRef.current = active;
  }, [active, events.length, expanded]);

  useEffect(() => () => {
    clearCollapseTimers();
  }, []);

  if (!events.length && !active) {
    return null;
  }

  const onToggleExpanded = () => {
    if (expanded) {
      scheduleCollapse(0);
      return;
    }

    clearCollapseTimers();
    setIsSettling(false);
    setIsCollapsing(false);
    setExpanded(true);
  };

  return (
    <section
      className={[
        "execution-steps",
        active ? "live" : "",
        expanded ? "expanded" : "",
        isSettling ? "settling" : "",
        isCollapsing ? "collapsing" : "",
        showCollapsedSummary ? "collapsed" : "",
      ].filter(Boolean).join(" ")}
    >
      <div className={showFocusedLayout ? "execution-panel live execution-panel-thoughts" : "execution-panel execution-panel-thoughts"}>
        <header className="execution-header execution-header-thinking">
          <div className="execution-status">
            <span className={active ? "execution-badge live" : "execution-badge"}>
              {active ? "Thinking" : "Thoughts"}
            </span>
            <div className="execution-summary">
              <strong>{heading}</strong>
              <span>{summary}</span>
            </div>
          </div>
          <div className="execution-header-actions">
            {events.length > 1 ? (
              <button
                type="button"
                className="execution-toggle"
                onClick={onToggleExpanded}
                aria-expanded={expanded}
              >
                {expanded ? "Hide history" : `Show history (${events.length - 1})`}
              </button>
            ) : null}
            <span className={active ? "execution-live-pill" : "execution-live-pill done"}>
              {active ? "Live" : "Done"}
            </span>
          </div>
        </header>

        <div className={[
          "execution-current",
          active ? "live" : "",
          latestEvent?.source === "model" ? "model" : "",
          latestEvent?.state === "error" || latestEvent?.type === "error" ? "error" : "",
        ].filter(Boolean).join(" ")}
        >
          <div
            className="execution-current-body execution-current-thought"
            key={`${latestEvent?.id || "idle"}:${latestNarration}`}
          >
            <div className="execution-current-topline">
              <span className="execution-current-kicker">
                <span className="execution-current-indicator" aria-hidden="true" />
                {getEventKicker(latestEvent)}
              </span>
              {latestEvent?.timestamp ? (
                <time dateTime={toDateTimeAttr(latestEvent.timestamp)}>
                  {formatTime(latestEvent.timestamp, { withSeconds: true })}
                </time>
              ) : null}
            </div>
            <strong>{active ? "What I'm doing now" : "Final thought"}</strong>
            <p className="execution-current-voice">{summary}</p>
            {latestSupportingDetail ? <div className="execution-detail">{latestSupportingDetail}</div> : null}
          </div>
        </div>

        {historyEvents.length ? (
          <div className="execution-history">
            <div className="execution-history-header">
              <span>Earlier thoughts</span>
              {hiddenCount > 0 ? (
                <button
                  type="button"
                  className="execution-more"
                  onClick={() => setExpanded(true)}
                >
                  Show {hiddenCount} more
                </button>
              ) : null}
            </div>
            <ol className="execution-history-list" ref={historyRef}>
              {historyEvents.map((event) => {
                const narration = getThinkingNarration(event);
                const supportingDetail = getSupportingDetail(event, narration, expanded);

                return (
                  <li key={event.id} className="execution-history-item">
                    <p className="execution-history-voice">{narration}</p>
                    <div className="execution-history-meta">
                      <span>{getEventKicker(event)}</span>
                      {event.timestamp ? (
                        <time dateTime={toDateTimeAttr(event.timestamp)}>
                          {formatTime(event.timestamp, { withSeconds: true })}
                        </time>
                      ) : null}
                    </div>
                    {supportingDetail ? <div className="execution-detail">{supportingDetail}</div> : null}
                  </li>
                );
              })}
            </ol>
          </div>
        ) : null}
      </div>

      {showCollapsedSummary ? (
        <button
          type="button"
          className="execution-collapsed"
          onClick={() => setExpanded(true)}
        >
          <span>Thinking</span>
          <strong>{summary}</strong>
          <span>Open</span>
        </button>
      ) : null}
    </section>
  );
}
