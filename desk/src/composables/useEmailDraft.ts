import { ref, computed, watch } from "vue";

export interface EmailDraft {
  content: string | null;
  to: string[];
  cc: string[];
  bcc: string[];
  attachments: any[];
  updatedAt: string;
}

/**
 * Ensures an array only contains strings, filtering out objects or invalid values
 */
function toStringArray(arr: unknown): string[] {
  if (!Array.isArray(arr)) return [];
  return arr
    .filter((item) => typeof item === "string" && item.trim() !== "")
    .map((item) => String(item).trim());
}

/**
 * Generate storage key for email draft
 */
function getDraftKey(ticketId: string | null, communicationId: string | null): string | null {
  if (!ticketId) return null;
  if (communicationId) {
    return `emailDraft_${ticketId}_${communicationId}`;
  }
  return `emailDraft_${ticketId}`;
}

/**
 * Read draft from localStorage
 */
function readDraft(key: string | null): EmailDraft | null {
  if (!key || typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw || raw === "null") return null;
    const parsed = JSON.parse(raw);
    if (!parsed) return null;
    return {
      content: parsed.content || null,
      to: toStringArray(parsed.to),
      cc: toStringArray(parsed.cc),
      bcc: toStringArray(parsed.bcc),
      attachments: Array.isArray(parsed.attachments) ? parsed.attachments : [],
      updatedAt: parsed.updatedAt || new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

/**
 * Write draft to localStorage
 */
function writeDraft(key: string | null, draft: EmailDraft | null): void {
  if (!key || typeof window === "undefined") return;
  if (!draft) {
    localStorage.removeItem(key);
    return;
  }
  const data = {
    content: draft.content,
    to: toStringArray(draft.to),
    cc: toStringArray(draft.cc),
    bcc: toStringArray(draft.bcc),
    attachments: draft.attachments || [],
    updatedAt: draft.updatedAt,
  };
  localStorage.setItem(key, JSON.stringify(data));
}

/**
 * Composable for managing email drafts in localStorage
 * Supports dynamic ticketId and communicationId
 */
export function useEmailDraft(ticketId: string | null, communicationId?: string | null) {
  // Store current IDs - these can be updated dynamically
  const currentTicketId = ref(ticketId);
  const currentCommunicationId = ref(communicationId || null);

  // Computed storage key
  const storageKey = computed(() =>
    getDraftKey(currentTicketId.value, currentCommunicationId.value)
  );

  // Reactive draft value - use a ref that gets updated when key changes
  const draft = ref<EmailDraft | null>(null);

  // Function to refresh draft from current storage key
  const refreshDraft = () => {
    const key = storageKey.value;
    draft.value = key ? readDraft(key) : null;
  };

  // Watch for storage key changes and refresh draft
  watch(storageKey, () => {
    refreshDraft();
  }, { immediate: true });

  function updateCommunicationId(newId: string | null) {
    currentCommunicationId.value = newId;
  }

  function saveDraft(data: {
    content: string | null;
    to: unknown[];
    cc: unknown[];
    bcc: unknown[];
    attachments: any[];
  }) {
    if (!storageKey.value) return;

    const draftData: EmailDraft = {
      content: data.content,
      to: toStringArray(data.to),
      cc: toStringArray(data.cc),
      bcc: toStringArray(data.bcc),
      attachments: Array.isArray(data.attachments) ? data.attachments : [],
      updatedAt: new Date().toISOString(),
    };

    writeDraft(storageKey.value, draftData);
    // Update the reactive draft ref to trigger reactivity
    draft.value = draftData;
  }

  function loadDraft(): EmailDraft | null {
    return draft.value;
  }

  function clearDraft() {
    writeDraft(storageKey.value, null);
    // Update the reactive draft ref to trigger reactivity
    draft.value = null;
  }

  function hasDraft(): boolean {
    const d = draft.value;
    if (!d) return false;

    // Only consider body content and attachments as a "real" draft.
    // Recipients alone (from initial props) are not a meaningful draft.
    const hasBody = !!(d.content && d.content.trim());
    const hasAttachments = !!(Array.isArray(d.attachments) && d.attachments.length);

    return hasBody || hasAttachments;
  }

  return {
    draft,
    storageKey,
    currentCommunicationId,
    updateCommunicationId,
    saveDraft,
    loadDraft,
    clearDraft,
    hasDraft,
  };
}
