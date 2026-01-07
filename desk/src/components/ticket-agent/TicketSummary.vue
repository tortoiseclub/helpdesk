<template>
  <div v-if="isAiEnabled" class="ticket-summary">
    <!-- Header -->
    <div
      class="flex items-center justify-between cursor-pointer py-2"
      @click="isExpanded = !isExpanded"
    >
      <div class="flex items-center gap-2">
        <LucideSparkles class="size-4 text-ink-gray-5" />
        <span class="text-sm font-medium text-ink-gray-7">AI Summary</span>
      </div>
      <div class="flex items-center gap-1">
        <Button
          v-if="hasSummary && !isLoading"
          variant="ghost"
          size="sm"
          class="h-6 w-6"
          @click.stop="regenerateSummary"
          :disabled="isLoading"
        >
          <template #icon>
            <LucideRefreshCw
              class="size-3.5"
              :class="{ 'animate-spin': isLoading }"
            />
          </template>
        </Button>
        <LucideChevronDown
          class="size-4 text-ink-gray-5 transition-transform"
          :class="{ 'rotate-180': isExpanded }"
        />
      </div>
    </div>

    <!-- Content -->
    <Transition name="expand">
      <div v-show="isExpanded" class="pb-3">
        <!-- Loading State -->
        <div
          v-if="isLoading"
          class="flex items-center gap-2 text-sm text-ink-gray-5 py-2"
        >
          <LoadingIndicator class="size-4" />
          <span>Generating summary...</span>
        </div>

        <!-- Summary Content -->
        <div
          v-else-if="hasSummary"
          class="text-sm text-ink-gray-7 leading-relaxed whitespace-pre-wrap bg-surface-gray-1 rounded-lg p-3"
        >
          {{ summaryText }}
        </div>

        <!-- Empty State -->
        <div v-else class="py-2">
          <p class="text-sm text-ink-gray-5 mb-2">
            No summary available yet.
          </p>
          <Button
            variant="outline"
            size="sm"
            @click="regenerateSummary"
            :disabled="isLoading"
          >
            <template #prefix>
              <LucideSparkles class="size-3.5" />
            </template>
            Generate Summary
          </Button>
        </div>

        <!-- Error State -->
        <div
          v-if="errorMessage"
          class="mt-2 text-sm text-red-600 bg-red-50 rounded p-2"
        >
          {{ errorMessage }}
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { TicketSymbol } from "@/types";
import { Button, createResource, LoadingIndicator } from "frappe-ui";
import { computed, inject, onMounted, ref, watch } from "vue";
import LucideChevronDown from "~icons/lucide/chevron-down";
import LucideRefreshCw from "~icons/lucide/refresh-cw";
import LucideSparkles from "~icons/lucide/sparkles";

const ticket = inject(TicketSymbol);

const isExpanded = ref(false);
const isLoading = ref(false);
const errorMessage = ref("");
const localSummary = ref("");

// Check if AI is enabled
const aiEnabledResource = createResource({
  url: "helpdesk.api.ai.is_ai_enabled",
  auto: true,
});

const isAiEnabled = computed(() => {
  return aiEnabledResource.data === true;
});

// Get summary from ticket or local state
const summaryText = computed(() => {
  // Prefer local summary (just generated) over ticket doc summary
  if (localSummary.value) {
    return localSummary.value;
  }
  return ticket?.value?.doc?.summary || "";
});

const hasSummary = computed(() => {
  return Boolean(summaryText.value && summaryText.value.trim().length > 0);
});

// Regenerate summary resource
const regenerateResource = createResource({
  url: "run_doc_method",
  makeParams: () => ({
    dt: "HD Ticket",
    dn: ticket?.value?.doc?.name,
    method: "regenerate_summary",
  }),
  onSuccess: (response: any) => {
    isLoading.value = false;
    errorMessage.value = "";
    
    // Frappe wraps the response in a 'message' property
    const data = response?.message || response;
    
    if (data?.success && data?.summary) {
      // Update local summary immediately for display
      localSummary.value = data.summary;
      // Also reload ticket to sync the doc
      ticket?.value?.reload();
    } else if (!data?.success) {
      errorMessage.value = data?.message || "Failed to generate summary";
    }
  },
  onError: (error: Error) => {
    isLoading.value = false;
    errorMessage.value = error?.message || "An error occurred while generating summary";
  },
});

function regenerateSummary() {
  if (isLoading.value || !ticket?.value?.doc?.name) return;
  
  isLoading.value = true;
  errorMessage.value = "";
  regenerateResource.submit();
}

// Watch for ticket changes to reset state
watch(
  () => ticket?.value?.doc?.name,
  () => {
    errorMessage.value = "";
    localSummary.value = ""; // Reset local summary when switching tickets
  }
);

onMounted(() => {
  aiEnabledResource.reload();
});
</script>

<style scoped>
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>

