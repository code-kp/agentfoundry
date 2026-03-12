import React, { useEffect, useMemo, useRef, useState } from "react";

import { TEAM_MODE_AGENT_ID } from "../lib/chatWorkspace";

function filterHiddenAgents(nodes) {
  return (Array.isArray(nodes) ? nodes : []).flatMap((node) => {
    if (!node || typeof node !== "object") {
      return [];
    }

    if (node.type === "agent") {
      return node.id === TEAM_MODE_AGENT_ID ? [] : [node];
    }

    const children = filterHiddenAgents(node.children || []);
    if (!children.length) {
      return [];
    }

    return [{
      ...node,
      children,
    }];
  });
}

function countAgents(nodes) {
  return (Array.isArray(nodes) ? nodes : []).reduce((count, node) => {
    if (node?.type === "agent") {
      return count + 1;
    }

    return count + countAgents(node?.children || []);
  }, 0);
}

function collectAgentIds(nodes) {
  return (Array.isArray(nodes) ? nodes : []).flatMap((node) => {
    if (!node || typeof node !== "object") {
      return [];
    }

    if (node.type === "agent") {
      return [node.id];
    }

    return collectAgentIds(node.children || []);
  });
}

function findAgentPath(nodes, agentId, path = []) {
  for (const node of Array.isArray(nodes) ? nodes : []) {
    if (node?.type === "agent" && node.id === agentId) {
      return path;
    }

    if (node?.type === "namespace") {
      const result = findAgentPath(node.children || [], agentId, [...path, node.name]);
      if (result) {
        return result;
      }
    }
  }

  return [];
}

function findNodesForPath(nodes, path) {
  let currentNodes = Array.isArray(nodes) ? nodes : [];

  for (const segment of Array.isArray(path) ? path : []) {
    const nextNode = currentNodes.find((node) => node?.type === "namespace" && node.name === segment);
    if (!nextNode) {
      return Array.isArray(nodes) ? nodes : [];
    }

    currentNodes = nextNode.children || [];
  }

  return currentNodes;
}

function buildNamespaceEntries(nodes) {
  return (Array.isArray(nodes) ? nodes : [])
    .filter((node) => node?.type === "namespace")
    .map((node) => ({
      ...node,
      agentIds: collectAgentIds(node.children || []),
      count: countAgents(node.children || []),
    }));
}

function getCloudSizeClass(entry, index) {
  const count = Number(entry?.count) || 0;
  const nameLength = String(entry?.name || "").length;

  if (count >= 10 || nameLength >= 18) {
    return "wide";
  }

  if ((index + count) % 5 === 0 || count >= 5) {
    return "medium";
  }

  if (count <= 2 && nameLength <= 8) {
    return "compact";
  }

  return "standard";
}

function formatFolderAvailability(count) {
  return count === 1
    ? "1 agent inside this folder"
    : `${count} agents inside this folder`;
}

function buildSearchResults(nodes, query, path = []) {
  const normalizedQuery = String(query || "").trim().toLowerCase();
  if (!normalizedQuery) {
    return [];
  }

  return (Array.isArray(nodes) ? nodes : []).flatMap((node) => {
    if (!node || typeof node !== "object") {
      return [];
    }

    if (node.type === "agent") {
      const fields = [node.name || "", node.id || "", node.description || ""];
      const matches = fields.some((value) => value.toLowerCase().includes(normalizedQuery));
      return matches ? [{
        type: "agent",
        agent: node,
        path,
      }] : [];
    }

    const nextPath = [...path, node.name];
    const matchesNamespace = String(node.name || "").toLowerCase().includes(normalizedQuery);
    const namespaceResult = matchesNamespace
      ? [{
        type: "namespace",
        name: node.name,
        path: nextPath,
        count: countAgents(node.children || []),
        agentIds: collectAgentIds(node.children || []),
      }]
      : [];

    return [
      ...namespaceResult,
      ...buildSearchResults(node.children || [], normalizedQuery, nextPath),
    ];
  });
}

function normalizeTeamSelection(agentIds, teamAgents) {
  const allowedIds = new Set(
    (Array.isArray(teamAgents) ? teamAgents : [])
      .map((agent) => String(agent?.id || "").trim())
      .filter(Boolean),
  );
  const seen = new Set();

  return (Array.isArray(agentIds) ? agentIds : []).filter((agentId) => {
    const normalizedId = String(agentId || "").trim();
    if (!allowedIds.has(normalizedId) || seen.has(normalizedId)) {
      return false;
    }

    seen.add(normalizedId);
    return true;
  });
}

function FolderIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M1.75 4.25A1.25 1.25 0 0 1 3 3h3.18c.42 0 .82.17 1.12.46l.86.84c.1.1.23.15.36.15H13A1.25 1.25 0 0 1 14.25 5.7v5.55A1.75 1.75 0 0 1 12.5 13H3.5a1.75 1.75 0 0 1-1.75-1.75V4.25Z"
        fill="currentColor"
      />
    </svg>
  );
}

function AgentIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M8 1.75a.75.75 0 0 1 .75.75v.92c1.8.3 3.25 1.86 3.25 3.76v2.57a2 2 0 0 1 1 1.74v.01a.75.75 0 0 1-.75.75H3.75a.75.75 0 0 1-.75-.75v-.01a2 2 0 0 1 1-1.74V7.18c0-1.9 1.45-3.46 3.25-3.76V2.5A.75.75 0 0 1 8 1.75Zm-1.9 6.1a.9.9 0 1 0 0 1.8.9.9 0 0 0 0-1.8Zm3.8 0a.9.9 0 1 0 0 1.8.9.9 0 0 0 0-1.8ZM6.2 11.2a.5.5 0 0 0 0 1h3.6a.5.5 0 0 0 0-1H6.2Z"
        fill="currentColor"
      />
    </svg>
  );
}

function TeamIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M5.15 4.1a1.65 1.65 0 1 1-3.3 0 1.65 1.65 0 0 1 3.3 0Zm9 0a1.65 1.65 0 1 1-3.3 0 1.65 1.65 0 0 1 3.3 0ZM8 5.2A2.05 2.05 0 1 1 8 1.1a2.05 2.05 0 0 1 0 4.1Zm-4.65 6c0-1.55 1.26-2.8 2.8-2.8h3.7c1.54 0 2.8 1.25 2.8 2.8v1.15c0 .41-.34.75-.75.75h-7.8a.75.75 0 0 1-.75-.75V11.2Zm-2.1 1.15v-.95c0-1.08.65-2 1.57-2.42a3.8 3.8 0 0 0-.42 1.76v1.61H2a.75.75 0 0 1-.75-.75Zm12.5 0a.75.75 0 0 1-.75.75h-.4v-1.61c0-.63-.15-1.22-.42-1.76.92.42 1.57 1.34 1.57 2.42v.95Z"
        fill="currentColor"
      />
    </svg>
  );
}

function renderPathBar({
  breadcrumbs,
  hasQuery,
  countText,
  onBack,
  onCrumbSelect,
  canGoBack,
}) {
  return (
    <div className="agent-directory-pathbar">
      <button
        type="button"
        className="agent-directory-back"
        onClick={onBack}
        disabled={!canGoBack || hasQuery}
      >
        Back
      </button>
      <div className="agent-directory-breadcrumbs" aria-label="Current directory">
        {breadcrumbs.map((segment, index) => (
          <React.Fragment key={`${segment}-${index}`}>
            {index > 0 ? <span className="agent-directory-separator">/</span> : null}
            <button
              type="button"
              className={index === breadcrumbs.length - 1 ? "agent-directory-crumb current" : "agent-directory-crumb"}
              disabled={hasQuery || index === breadcrumbs.length - 1}
              onClick={() => onCrumbSelect(index)}
            >
              {segment}
            </button>
          </React.Fragment>
        ))}
      </div>
      <span className="agent-directory-count">{countText}</span>
    </div>
  );
}

export function AgentPickerDrawer({
  isOpen,
  isLoading,
  mode,
  selectedAgentId,
  selectedTeamAgentIds,
  teamAgents,
  teamModeAgent,
  tree,
  onClose,
  onSelectAgent,
  onTeamAgentIdsChange,
  searchText,
  onSearchTextChange,
}) {
  const searchInputRef = useRef(null);
  const [activeView, setActiveView] = useState("browse");
  const [browsePath, setBrowsePath] = useState([]);
  const [teamPath, setTeamPath] = useState([]);
  const isNewChatMode = mode === "new_chat";
  const hasQuery = Boolean(searchText.trim());
  const visibleTree = useMemo(
    () => filterHiddenAgents(tree),
    [tree],
  );
  const browseNodes = useMemo(
    () => findNodesForPath(visibleTree, browsePath),
    [browsePath, visibleTree],
  );
  const teamNodes = useMemo(
    () => findNodesForPath(visibleTree, teamPath),
    [teamPath, visibleTree],
  );
  const browseNamespaceEntries = useMemo(
    () => buildNamespaceEntries(browseNodes),
    [browseNodes],
  );
  const teamNamespaceEntries = useMemo(
    () => buildNamespaceEntries(teamNodes),
    [teamNodes],
  );
  const browseAgentEntries = useMemo(
    () => browseNodes.filter((node) => node?.type === "agent"),
    [browseNodes],
  );
  const teamAgentEntries = useMemo(
    () => teamNodes.filter((node) => node?.type === "agent"),
    [teamNodes],
  );
  const searchResults = useMemo(
    () => buildSearchResults(visibleTree, searchText),
    [searchText, visibleTree],
  );
  const searchedNamespaces = useMemo(
    () => searchResults.filter((entry) => entry.type === "namespace"),
    [searchResults],
  );
  const searchedAgents = useMemo(
    () => searchResults.filter((entry) => entry.type === "agent"),
    [searchResults],
  );
  const normalizedSelectedTeamIds = useMemo(
    () => normalizeTeamSelection(selectedTeamAgentIds, teamAgents),
    [selectedTeamAgentIds, teamAgents],
  );
  const selectedTeamSet = useMemo(
    () => new Set(normalizedSelectedTeamIds),
    [normalizedSelectedTeamIds],
  );
  const teamModeAlreadyActive = selectedAgentId === TEAM_MODE_AGENT_ID;
  const browseBreadcrumbs = browsePath.length ? ["ROOT", ...browsePath] : ["ROOT"];
  const teamBreadcrumbs = teamPath.length ? ["ROOT", ...teamPath] : ["ROOT"];

  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    searchInputRef.current?.focus();

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    if (selectedAgentId === TEAM_MODE_AGENT_ID && teamModeAgent) {
      setActiveView("team");
      setTeamPath([]);
      return;
    }

    setActiveView("browse");
    setBrowsePath(findAgentPath(visibleTree, selectedAgentId));
  }, [isOpen, selectedAgentId, teamModeAgent, visibleTree]);

  const handleSetTeamSelection = (agentIds, checked) => {
    const idsToToggle = normalizeTeamSelection(agentIds, teamAgents);
    const nextSelection = checked
      ? normalizeTeamSelection([...normalizedSelectedTeamIds, ...idsToToggle], teamAgents)
      : normalizeTeamSelection(
        normalizedSelectedTeamIds.filter((value) => !idsToToggle.includes(value)),
        teamAgents,
      );

    onTeamAgentIdsChange(nextSelection);
  };

  const getSelectionState = (agentIds) => {
    const selectedCount = normalizeTeamSelection(agentIds, teamAgents)
      .filter((agentId) => selectedTeamSet.has(agentId))
      .length;
    const totalCount = normalizeTeamSelection(agentIds, teamAgents).length;

    return {
      checked: Boolean(totalCount) && selectedCount === totalCount,
      indeterminate: selectedCount > 0 && selectedCount < totalCount,
      selectedCount,
      totalCount,
    };
  };

  const getSelectionLabel = (selection) => {
    if (selection.checked) {
      return "Selected";
    }

    if (selection.indeterminate) {
      return `${selection.selectedCount}/${selection.totalCount}`;
    }

    return "Select";
  };

  const renderDirectorySection = (title, items, renderItem, options = {}) => {
    if (!items.length) {
      return null;
    }

    const listClassName = (() => {
      if (options.variant === "cloud") {
        return "agent-directory-cloud";
      }

      if (options.variant === "fixed-cloud") {
        return "agent-directory-agent-cloud";
      }

      return "agent-directory-list";
    })();

    return (
      <section className="agent-directory-section">
        <div className="agent-directory-section-header">
          <h3>{title}</h3>
          <span>{items.length}</span>
        </div>
        <div className={listClassName}>
          {items.map((item, index) => renderItem(item, index))}
        </div>
      </section>
    );
  };

  const renderBrowseNamespaceItem = (entry, index) => (
    <button
      key={`browse-folder-${entry.path ? entry.path.join("/") : entry.name}`}
      type="button"
      className={`agent-directory-cloud-card ${getCloudSizeClass(entry, index)}`}
      onClick={() => setBrowsePath(entry.path || [...browsePath, entry.name])}
    >
      <span className="agent-directory-item-icon folder"><FolderIcon /></span>
      <span className="agent-directory-item-copy">
        <strong>{entry.name}</strong>
        <span>{formatFolderAvailability(entry.count)}</span>
      </span>
    </button>
  );

  const renderBrowseAgentItem = (agent, subtitle = "") => {
    const selected = agent.id === selectedAgentId;

    return (
      <button
        key={`browse-agent-${agent.id}`}
        type="button"
        className={[
          "agent-directory-cloud-card",
          "agent-directory-agent-card",
          selected ? "selected" : "",
        ].filter(Boolean).join(" ")}
        aria-pressed={selected}
        onClick={() => onSelectAgent(agent.id)}
      >
        <div className="agent-card-main">
          <span className="agent-directory-item-icon agent"><AgentIcon /></span>
          <span className="agent-directory-item-copy">
            <strong>{agent.name || agent.id}</strong>
            {subtitle ? <span>{subtitle}</span> : null}
          </span>
        </div>
      </button>
    );
  };

  const renderTeamNamespaceItem = (entry, index) => {
    const selection = getSelectionState(entry.agentIds);
    const availabilityLabel = formatFolderAvailability(entry.count);
    const selectionMeta = selection.checked
      ? `${selection.totalCount} selected`
      : selection.indeterminate
        ? `${selection.selectedCount}/${selection.totalCount} selected`
        : "";

    return (
      <div
        key={`team-namespace-${entry.path ? entry.path.join("/") : entry.name}`}
        className={`agent-team-cloud-card ${getCloudSizeClass(entry, index)} ${selection.checked ? "checked" : ""}`}
      >
        <div className="agent-card-main">
          <span className="agent-directory-item-icon folder"><FolderIcon /></span>
          <span className="agent-directory-item-copy">
            <strong>{entry.name}</strong>
            <span>{availabilityLabel}</span>
          </span>
        </div>
        <div className="agent-card-footer">
          {selectionMeta ? <span className="agent-team-card-meta">{selectionMeta}</span> : <span />}
          <div className="agent-team-card-actions">
            <button
              type="button"
              className="agent-team-link"
              onClick={() => {
                setTeamPath(entry.path || [...teamPath, entry.name]);
                onSearchTextChange("");
              }}
            >
              Open
            </button>
            <button
              type="button"
              className={[
                "agent-team-link",
                "pick",
                selection.checked ? "active" : "",
                selection.indeterminate ? "partial" : "",
              ].filter(Boolean).join(" ")}
              onClick={() => handleSetTeamSelection(entry.agentIds, !selection.checked)}
            >
              {getSelectionLabel(selection)}
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderTeamAgentItem = (agent, subtitle = "") => {
    const checked = selectedTeamSet.has(agent.id);

    return (
      <button
        key={`team-agent-${agent.id}`}
        type="button"
        className={[
          "agent-team-cloud-card",
          "agent-team-agent-card",
          checked ? "checked" : "",
        ].filter(Boolean).join(" ")}
        aria-pressed={checked}
        onClick={() => handleSetTeamSelection([agent.id], !checked)}
      >
        <div className="agent-card-main">
          <span className="agent-directory-item-icon team"><TeamIcon /></span>
          <span className="agent-directory-item-copy">
            <strong>{agent.name || agent.id}</strong>
            {subtitle ? <span>{subtitle}</span> : null}
          </span>
        </div>
      </button>
    );
  };

  return (
    <div
      className={[
        "agent-drawer",
        isOpen ? "open" : "",
        isNewChatMode ? "new-chat" : "",
      ].filter(Boolean).join(" ")}
      aria-hidden={!isOpen}
    >
      <button
        type="button"
        className="agent-drawer-backdrop"
        onClick={onClose}
        aria-label="Close agent selector"
      />

      <aside className="agent-drawer-panel">
        <header className="agent-drawer-header">
          <div>
            <span className="sidebar-label">Agents</span>
            <h2>{isNewChatMode ? "Choose how this chat should start" : "Change the active agent"}</h2>
            <p>
              {isNewChatMode
                ? "Browse folders, pick a single agent, or build a Team Mode group from folders and individual agents."
                : "Use the same selector to swap agents or reconfigure Team Mode for this conversation."}
            </p>
          </div>
          <button
            type="button"
            className="sidebar-action"
            onClick={onClose}
          >
            Close
          </button>
        </header>

        <div className="agent-drawer-toolbar">
          <div className="agent-drawer-tabs" role="tablist" aria-label="Agent selector views">
            <button
              type="button"
              role="tab"
              aria-selected={activeView === "browse"}
              className={activeView === "browse" ? "agent-drawer-tab active" : "agent-drawer-tab"}
              onClick={() => {
                setActiveView("browse");
                onSearchTextChange("");
              }}
            >
              Directory
            </button>
            {teamModeAgent ? (
              <button
                type="button"
                role="tab"
                aria-selected={activeView === "team"}
                className={activeView === "team" ? "agent-drawer-tab active" : "agent-drawer-tab"}
                onClick={() => {
                  setActiveView("team");
                  onSearchTextChange("");
                }}
              >
                Team Mode
              </button>
            ) : null}
          </div>

          <section className="agent-drawer-search">
            <label className="sr-only" htmlFor="agent-picker-search">
              {activeView === "team" ? "Search directories or agents for Team Mode" : "Search directories or agents"}
            </label>
            <input
              id="agent-picker-search"
              ref={searchInputRef}
              type="text"
              placeholder={activeView === "team" ? "Search directories or agents for Team Mode" : "Search directories or agents"}
              value={searchText}
              disabled={isLoading}
              onChange={(event) => onSearchTextChange(event.target.value)}
            />
          </section>
        </div>

        <div className="agent-drawer-content">
          {isLoading ? (
            <div className="agent-drawer-loading">
              <span className="agent-drawer-loading-dot" aria-hidden="true" />
              <span>Loading live agent directory...</span>
            </div>
          ) : null}

          {!isLoading && activeView === "browse" ? (
            <div className="agent-directory-content">
              {renderPathBar({
                breadcrumbs: browseBreadcrumbs,
                hasQuery,
                countText: hasQuery
                  ? `${searchResults.length} results`
                  : `${browseNamespaceEntries.length + browseAgentEntries.length} items`,
                canGoBack: browsePath.length > 0,
                onBack: () => setBrowsePath((current) => current.slice(0, -1)),
                onCrumbSelect: (index) => setBrowsePath(browsePath.slice(0, index)),
              })}

              {hasQuery ? (
                <div className="agent-directory-sections">
                  {renderDirectorySection("Folders", searchedNamespaces, (entry, index) => (
                    <button
                      key={`browse-namespace-${entry.path.join("/")}`}
                      type="button"
                      className={`agent-directory-cloud-card ${getCloudSizeClass(entry, index)}`}
                      onClick={() => {
                        setBrowsePath(entry.path);
                        onSearchTextChange("");
                      }}
                    >
                      <span className="agent-directory-item-icon folder"><FolderIcon /></span>
                      <span className="agent-directory-item-copy">
                        <strong>{entry.name}</strong>
                        <span>{formatFolderAvailability(entry.count)}</span>
                      </span>
                    </button>
                  ), { variant: "cloud" })}
                  {renderDirectorySection("Agents", searchedAgents, (entry) => renderBrowseAgentItem(
                    entry.agent,
                    entry.agent.description || "",
                  ), { variant: "fixed-cloud" })}
                  {!searchResults.length ? (
                    <div className="agent-directory-empty">
                      No folders or agents match the current search.
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="agent-directory-sections">
                  {renderDirectorySection("Folders", browseNamespaceEntries, renderBrowseNamespaceItem, { variant: "cloud" })}
                  {renderDirectorySection("Agents", browseAgentEntries, (entry) => renderBrowseAgentItem(
                    entry,
                    entry.description || "",
                  ), { variant: "fixed-cloud" })}
                  {!browseNamespaceEntries.length && !browseAgentEntries.length ? (
                    <div className="agent-directory-empty">
                      This folder is empty.
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          ) : null}

          {!isLoading && activeView === "team" ? (
            <div className="agent-team-content">
              <div className="agent-team-toolbar">
                <div className="agent-team-actions">
                  <span className="agent-team-count">{normalizedSelectedTeamIds.length} selected</span>
                  <button
                    type="button"
                    className="agent-team-action"
                    disabled={!teamAgents.length}
                    onClick={() => onTeamAgentIdsChange(teamAgents.map((agent) => agent.id))}
                  >
                    All
                  </button>
                  <button
                    type="button"
                    className="agent-team-action"
                    disabled={!normalizedSelectedTeamIds.length}
                    onClick={() => onTeamAgentIdsChange([])}
                  >
                    None
                  </button>
                </div>
              </div>

              {renderPathBar({
                breadcrumbs: teamBreadcrumbs,
                hasQuery,
                countText: hasQuery
                  ? `${searchResults.length} results`
                  : `${teamNamespaceEntries.length + teamAgentEntries.length} items`,
                canGoBack: teamPath.length > 0,
                onBack: () => setTeamPath((current) => current.slice(0, -1)),
                onCrumbSelect: (index) => setTeamPath(teamPath.slice(0, index)),
              })}

              {hasQuery ? (
                <div className="agent-directory-sections">
                  {renderDirectorySection("Folders", searchedNamespaces, renderTeamNamespaceItem, { variant: "cloud" })}
                  {renderDirectorySection("Agents", searchedAgents, (entry) => renderTeamAgentItem(
                    entry.agent,
                    entry.agent.description || "",
                  ), { variant: "fixed-cloud" })}
                  {!searchResults.length ? (
                    <div className="agent-directory-empty">
                      No folders or agents match the current search.
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="agent-directory-sections">
                  {renderDirectorySection("Folders", teamNamespaceEntries, renderTeamNamespaceItem, { variant: "cloud" })}
                  {renderDirectorySection("Agents", teamAgentEntries, (entry) => renderTeamAgentItem(
                    entry,
                    entry.description || "",
                  ), { variant: "fixed-cloud" })}
                  {!teamNamespaceEntries.length && !teamAgentEntries.length ? (
                    <div className="agent-directory-empty">
                      This folder is empty.
                    </div>
                  ) : null}
                </div>
              )}

              <div className="agent-team-footer">
                <p className="agent-team-note">
                  {teamModeAgent?.description || "Team Mode stays constrained to the directories and agents selected here."}
                </p>
                <button
                  type="button"
                  className="conversation-dialog-button primary"
                  disabled={!normalizedSelectedTeamIds.length}
                  onClick={() => onSelectAgent(TEAM_MODE_AGENT_ID, { teamAgentIds: normalizedSelectedTeamIds })}
                >
                  {teamModeAlreadyActive ? "Update team" : isNewChatMode ? "Start with Team Mode" : "Use Team Mode"}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
