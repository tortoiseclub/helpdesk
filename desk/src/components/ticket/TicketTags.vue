<template>
  <div class="ticket-tags">
    <!-- Header with label and add button -->
    <div class="mb-1.5 flex items-center justify-between">
      <label class="text-xs text-gray-600">Tags</label>
      <div class="flex items-center gap-1">
        <Button
          v-if="canEdit && showInput"
          variant="ghost"
          size="sm"
          @click="cancelInput"
          title="Cancel"
        >
          <template #icon>
            <LucideX class="size-3" />
          </template>
        </Button>
        <Button
          v-if="canEdit && !showInput && isAiEnabled"
          variant="ghost"
          size="sm"
          @click="autoTagWithAI"
          :disabled="isAutoTagging"
          title="Auto-tag with AI"
        >
          <template #icon>
            <LucideLoader2 v-if="isAutoTagging" class="size-3 animate-spin" />
            <LucideSparkles v-else class="size-3" />
          </template>
        </Button>
      <Button
        v-if="canEdit && !showInput"
        variant="ghost"
        size="sm"
          @click="openInput"
          title="Add tag"
      >
        <template #prefix>
          <LucidePlus class="size-3" />
        </template>
      </Button>
      </div>
    </div>

    <!-- Display existing tags -->
    <div v-if="tags.length > 0" class="flex flex-wrap gap-1.5">
      <Badge
        v-for="tag in tags"
        :key="tag"
        :label="tag"
        theme="gray"
        variant="subtle"
      >
        <template v-if="canEdit" #suffix>
          <button
            class="ml-1 hover:text-ink-gray-9 transition-colors"
            @click.stop="removeTag(tag)"
            :disabled="tagBeingRemoved === tag"
          >
            <LucideX v-if="tagBeingRemoved !== tag" class="size-3" />
            <LucideLoader2 v-else class="size-3 animate-spin" />
          </button>
        </template>
      </Badge>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!showInput"
      class="text-sm text-ink-gray-4"
    >
      No tags
    </div>

    <!-- Add new tag dropdown -->
    <Autocomplete
      v-if="canEdit && showInput"
      class="mt-2"
      :options="tagOptionsWithCreate"
      placeholder="Search or create tag..."
      :autofocus="true"
      @update:modelValue="handleTagSelection"
      @update:query="handleQueryUpdate"
    >
      <template #prefix>
        <LucideSearch class="size-4 text-ink-gray-4" />
      </template>
      <template #item="{ item }">
        <div class="flex items-center gap-2">
          <LucidePlus v-if="item.isCreate" class="size-3.5 text-ink-gray-5" />
          <LucideTag v-else class="size-3.5 text-ink-gray-5" />
          <span :class="item.isCreate ? 'text-ink-gray-7' : ''">
            {{ item.isCreate ? `Create "${item.value}"` : item.label }}
          </span>
        </div>
      </template>
    </Autocomplete>
  </div>
</template>

<script setup lang="ts">
import { Autocomplete, Badge, Button, toast } from "frappe-ui";
import { computed, onMounted, ref } from "vue";
import LucidePlus from "~icons/lucide/plus";
import LucideX from "~icons/lucide/x";
import LucideLoader2 from "~icons/lucide/loader-2";
import LucideSparkles from "~icons/lucide/sparkles";
import LucideSearch from "~icons/lucide/search";
import LucideTag from "~icons/lucide/tag";
import { createResource } from "frappe-ui";

const props = defineProps<{
  ticketId: string;
  modelValue: string[];
  canEdit?: boolean;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string[]];
}>();

const tags = computed(() => props.modelValue || []);

const showInput = ref(false);
const searchQuery = ref("");
const tagBeingRemoved = ref("");
const isAutoTagging = ref(false);

// Check if AI tag annotation is enabled
const aiTagAnnotationEnabledResource = createResource({
  url: "helpdesk.api.ai.is_ai_tag_annotation_enabled",
  auto: true,
});

const isAiEnabled = computed(() => {
  return aiTagAnnotationEnabledResource.data === true;
});

// Resource to auto-tag with AI
const autoTagResource = createResource({
  url: "run_doc_method",
  onSuccess: (response: any) => {
    isAutoTagging.value = false;
    const data = response?.message || response;
    
    if (data?.success) {
      const tagsAdded = data.tags_added || [];
      const alreadyPresent = data.tags_already_present || [];
      
      if (tagsAdded.length > 0) {
        // Update the tags list
        const newTags = [...tags.value, ...tagsAdded];
        emit("update:modelValue", newTags);
        toast.success(`Added ${tagsAdded.length} tag(s): ${tagsAdded.join(", ")}`);
      } else if (alreadyPresent.length > 0) {
        toast.info("Suggested tags are already present on this ticket");
      } else {
        toast.info(data.message || "No relevant tags found");
      }
    } else {
      toast.error(data?.message || "Failed to auto-tag");
    }
  },
  onError: (error: Error) => {
    isAutoTagging.value = false;
    toast.error(error?.message || "Failed to auto-tag with AI");
  },
});

function autoTagWithAI() {
  if (isAutoTagging.value || !props.ticketId) return;
  
  isAutoTagging.value = true;
  autoTagResource.submit({
    dt: "HD Ticket",
    dn: props.ticketId,
    method: "annotate_tags",
  });
}

// Resource to get tag suggestions
const tagSuggestionsResource = createResource({
  url: "frappe.desk.doctype.tag.tag.get_tags",
  transform: (data: string[]) =>
    (data || []).map((tag) => ({
      label: tag,
      value: tag,
    })),
});

// Filtered tag suggestions (excluding already added tags)
const tagSuggestions = computed(() => {
  const suggestions = tagSuggestionsResource.data || [];
  return suggestions.filter((s) => !tags.value.includes(s.value));
});

// Options with "Create" option when search doesn't match
const tagOptionsWithCreate = computed(() => {
  const query = searchQuery.value.trim();
  const suggestions = tagSuggestions.value;
  
  // If no query, just return suggestions
  if (!query) return suggestions;
  
  // Check if query exactly matches an existing tag (case-insensitive)
  const queryLower = query.toLowerCase();
  const exactMatch = suggestions.some((s) => s.value.toLowerCase() === queryLower);
  const alreadyOnTicket = tags.value.some((t) => t.toLowerCase() === queryLower);
  
  // If no exact match and not already on ticket, add "Create" option
  if (!exactMatch && !alreadyOnTicket) {
    return [
      ...suggestions,
      { label: query, value: query, isCreate: true },
    ];
  }
  
  return suggestions;
});

function fetchTags(searchText = "") {
  tagSuggestionsResource.submit({
    doctype: "HD Ticket",
    txt: searchText,
  });
}

// Handle search query updates from Autocomplete
function handleQueryUpdate(query: string) {
  searchQuery.value = query;
  fetchTags(query);
}

// Handle tag selection from Autocomplete
function handleTagSelection(option: { label: string; value: string; isCreate?: boolean } | null) {
  if (!option) return;
  
  const tagValue = option.value;
  if (!tagValue || !props.ticketId) return;
  
  // Check if already on ticket
  if (tags.value.some((t) => t.toLowerCase() === tagValue.toLowerCase())) {
    toast.warning("Tag already added to this ticket");
    return;
  }
  
  // Add the tag (works for both existing and new tags)
  tagBeingAdded.value = tagValue;
  addTagResource.submit({
    tag: tagValue,
    dt: "HD Ticket",
    dn: props.ticketId,
  });
  
  // Close the dropdown
  showInput.value = false;
  searchQuery.value = "";
}

// Store tag being added for use in callbacks
const tagBeingAdded = ref("");

// Resource to add tag
const addTagResource = createResource({
  url: "frappe.desk.doctype.tag.tag.add_tag",
  onSuccess: () => {
    const addedTag = tagBeingAdded.value;
    const newTags = [...tags.value, addedTag];
    emit("update:modelValue", newTags);
    toast.success(`Tag "${addedTag}" added`);
    tagBeingAdded.value = "";
  },
  onError: (error) => {
    tagBeingAdded.value = "";
    toast.error(`Failed to add tag: ${error.message}`);
  },
});

// Resource to remove tag
const removeTagResource = createResource({
  url: "frappe.desk.doctype.tag.tag.remove_tag",
  onSuccess: () => {
    const removedTag = tagBeingRemoved.value;
    const newTags = tags.value.filter((t) => t !== removedTag);
    emit("update:modelValue", newTags);
    toast.success(`Tag "${removedTag}" removed`);
    tagBeingRemoved.value = "";
  },
  onError: (error) => {
    tagBeingRemoved.value = "";
    toast.error(`Failed to remove tag: ${error.message}`);
  },
});

function removeTag(tag: string) {
  if (!props.ticketId) {
    toast.error("Cannot remove tag: ticket ID is missing");
    return;
  }

  if (tagBeingRemoved.value) {
    // Already removing a tag, wait
    return;
  }

  tagBeingRemoved.value = tag;
  removeTagResource.submit({
    tag: tag,
    dt: "HD Ticket",
    dn: props.ticketId,
  });
}

function openInput() {
  showInput.value = true;
  searchQuery.value = "";
  fetchTags();
}

function cancelInput() {
  showInput.value = false;
  searchQuery.value = "";
}

onMounted(() => {
  aiTagAnnotationEnabledResource.reload();
});
</script>

<style scoped>
.ticket-tags :deep(.badge) {
  cursor: default;
}

.ticket-tags :deep(.badge button) {
  cursor: pointer;
}

.ticket-tags :deep(.badge button:disabled) {
  cursor: wait;
}
</style>
