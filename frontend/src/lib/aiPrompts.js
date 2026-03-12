export function buildConversationTitleInstructions() {
  return [
    "Generate a concise conversation title for a chat workspace from the user's opening request.",
    "Return only the title text.",
    "Keep it specific, concrete, and professional.",
    "Use 3 to 7 words.",
    "Do not use quotes, markdown, emojis, or ending punctuation.",
    "Do not prefix with Title: or Conversation:.",
    "Focus on the user's main intent.",
  ].join("\n");
}

export function buildConversationTitleMessage(requestText) {
  return [
    "Create a concise title for this conversation from this opening user request:",
    String(requestText || "").trim(),
    "Return only the title.",
  ].join("\n");
}

export function buildConversationRetitleInstructions() {
  return [
    "Generate a concise conversation title for a chat workspace from the conversation summary below.",
    "Return only the title text.",
    "Keep it specific, concrete, and professional.",
    "Use 3 to 7 words.",
    "Reflect the current focus of the conversation, not just the opening request.",
    "Do not use quotes, markdown, emojis, or ending punctuation.",
    "Do not prefix with Title: or Conversation:.",
  ].join("\n");
}

export function buildConversationRetitleMessage(messages) {
  const conversationMessages = Array.isArray(messages)
    ? messages.filter((message) => (
      ["user", "assistant"].includes(message?.role)
        && String(message?.text || "").trim()
    ))
    : [];

  if (!conversationMessages.length) {
    return "";
  }

  const openingUserMessage = conversationMessages.find((message) => message.role === "user") || null;
  const latestUserMessage = [...conversationMessages]
    .reverse()
    .find((message) => message.role === "user") || null;
  const latestAssistantMessage = [...conversationMessages]
    .reverse()
    .find((message) => message.role === "assistant") || null;
  const recentTurns = conversationMessages
    .slice(-6)
    .map((message, index) => `${index + 1}. ${message.role === "user" ? "User" : "Assistant"}: ${truncatePromptText(message.text, 220)}`);

  return [
    "Conversation summary:",
    openingUserMessage
      ? `Opening request: ${truncatePromptText(openingUserMessage.text, 240)}`
      : "",
    latestUserMessage && latestUserMessage !== openingUserMessage
      ? `Latest user focus: ${truncatePromptText(latestUserMessage.text, 240)}`
      : "",
    latestAssistantMessage
      ? `Latest assistant response: ${truncatePromptText(latestAssistantMessage.text, 240)}`
      : "",
    recentTurns.length ? "Recent turns:" : "",
    ...recentTurns,
    "Return only the title.",
  ]
    .filter(Boolean)
    .join("\n");
}

function truncatePromptText(value, maxChars) {
  const normalized = String(value || "").replace(/\s+/g, " ").trim();
  if (normalized.length <= maxChars) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(0, maxChars - 1)).trimEnd()}…`;
}
