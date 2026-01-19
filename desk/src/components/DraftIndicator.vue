<template>
  <div
    v-if="draftData"
    class="flex items-center justify-between gap-3 border-t px-6 md:px-10 py-3 bg-gray-50 hover:bg-gray-100 transition-colors cursor-pointer"
    @click="expand"
  >
    <div class="flex items-center gap-3 flex-1 min-w-0">
      <div class="flex items-center gap-2 text-sm text-gray-600">
        <FeatherIcon name="file-text" class="h-4 w-4 text-gray-500" />
        <span class="font-medium">Draft saved</span>
        <span v-if="draftData.updatedAt" class="text-xs text-gray-500">
          {{ formatTime(draftData.updatedAt) }}
        </span>
      </div>
      <div class="flex items-center gap-2 text-xs text-gray-500 min-w-0">
        <span v-if="draftData.to.length" class="truncate">
          To: {{ draftData.to.join(", ") }}
        </span>
        <span v-if="draftData.cc.length" class="truncate">
          CC: {{ draftData.cc.join(", ") }}
        </span>
        <span v-if="draftData.bcc.length" class="truncate">
          BCC: {{ draftData.bcc.join(", ") }}
        </span>
        <span v-if="draftData.attachments.length" class="flex items-center gap-1">
          <FeatherIcon name="paperclip" class="h-3 w-3" />
          {{ draftData.attachments.length }}
        </span>
      </div>
    </div>
    <div class="flex items-center gap-2">
      <Button
        variant="ghost"
        label="Discard"
        @click.stop="handleDiscard"
        class="text-gray-600"
      />
      <Button
        variant="ghost"
        label="Continue"
        @click.stop="expand"
        class="text-gray-700"
      >
        <template #suffix>
          <FeatherIcon name="chevron-up" class="h-4 w-4" />
        </template>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { FeatherIcon, Button } from "frappe-ui";
import { useEmailDraft } from "@/composables/useEmailDraft";
import { computed } from "vue";

const props = defineProps({
  ticketId: {
    type: String,
    default: null,
  },
  communicationId: {
    type: String,
    default: null,
  },
});

const emit = defineEmits(["expand", "discard"]);

const { loadDraft, clearDraft } = useEmailDraft(props.ticketId, props.communicationId);

// Load draft data reactively through the composable
const draftData = computed(() => {
  return loadDraft();
});

function expand() {
  emit("expand");
}

function handleDiscard() {
  clearDraft();
  emit("discard");
}

function formatTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}
</script>
