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

    <!-- Add new tag input -->
    <div v-if="canEdit && showInput" class="relative mt-1.5">
    <Autocomplete
      v-model="newTagInput"
      :options="tagSuggestions"
        placeholder="Type to add or create tag..."
        @update:modelValue="handleTagSelect"
    >
      <template #target="{ togglePopover }">
        <FormControl
          ref="tagInputRef"
          v-model="newTagInput"
          type="text"
            placeholder="Type to add or create tag..."
          @keydown.enter.prevent="addNewTag"
          @keydown.escape="cancelInput"
            @input="handleInput"
          @focus="togglePopover"
        />
      </template>
        <template #footer v-if="inputText && !tagExists">
          <div class="border-t border-outline-gray-2">
            <button
              class="w-full px-3 py-2 text-left text-sm text-ink-gray-7 hover:bg-surface-gray-2 flex items-center gap-2"
              @click="addNewTag"
            >
              <LucidePlus class="size-3" />
              Create "{{ inputText }}"
            </button>
          </div>
        </template>
        <template #empty v-if="!tagSuggestionsResource.loading">
          <div class="px-3 py-2 text-sm text-ink-gray-5">
            {{ inputText ? 'No matching tags found' : 'Start typing to search tags' }}
          </div>
        </template>
    </Autocomplete>
      <div
        v-if="addTagResource.loading"
        class="absolute right-2 top-1/2 -translate-y-1/2"
      >
        <LucideLoader2 class="size-4 animate-spin text-ink-gray-5" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Autocomplete, Badge, Button, FormControl, toast } from "frappe-ui";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import LucidePlus from "~icons/lucide/plus";
import LucideX from "~icons/lucide/x";
import LucideLoader2 from "~icons/lucide/loader-2";
import LucideSparkles from "~icons/lucide/sparkles";
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
const newTagInput = ref<string | { label: string; value: string }>("");
const tagInputRef = ref<InstanceType<typeof FormControl> | null>(null);
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

// Helper to get string value from input (handles both string and object)
function getInputValue(): string {
  const val = newTagInput.value;
  if (typeof val === "string") {
    return val.trim();
  }
  if (val && typeof val === "object" && "value" in val) {
    return String(val.value).trim();
  }
  return "";
}

// Computed for template use
const inputText = computed(() => getInputValue());

// Check if the current input already exists as a tag
const tagExists = computed(() => {
  const input = getInputValue().toLowerCase();
  return tags.value.some((t) => t.toLowerCase() === input);
});

// Resource to get tag suggestions
const tagSuggestionsResource = createResource({
  url: "frappe.desk.doctype.tag.tag.get_tags",
  transform: (data: string[]) =>
    (data || []).map((tag) => ({
      label: tag,
      value: tag,
    })),
});

const tagSuggestions = computed(() => {
  const suggestions = tagSuggestionsResource.data || [];
  // Filter out already added tags
  return suggestions.filter((s) => !tags.value.includes(s.value));
});

function fetchTags(searchText = "") {
  tagSuggestionsResource.submit({
    doctype: "HD Ticket",
    txt: searchText,
  });
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
    newTagInput.value = "";
    tagBeingAdded.value = "";
    // Refresh suggestions to include the new tag
    fetchTags();
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

function handleInput() {
  fetchTags(getInputValue());
}

function handleTagSelect(value: string | { label: string; value: string }) {
  // Extract the actual tag string from selection
  const tagValue = typeof value === "string" ? value : value?.value;
  if (tagValue) {
    newTagInput.value = tagValue;
    addNewTag();
  }
}

function addNewTag() {
  const tagValue = getInputValue();
  
  if (!tagValue) {
    return;
  }

  if (!props.ticketId) {
    toast.error("Cannot add tag: ticket ID is missing");
    return;
  }

  // Check if tag already exists on this ticket
  if (tags.value.some((t) => t.toLowerCase() === tagValue.toLowerCase())) {
    toast.warning("Tag already added to this ticket");
    newTagInput.value = "";
    return;
  }

  // Store for use in callback
  tagBeingAdded.value = tagValue;

  // Add the tag
  addTagResource.submit({
    tag: tagValue,
    dt: "HD Ticket",
    dn: props.ticketId,
  });
}

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
  fetchTags();
}

function cancelInput() {
  newTagInput.value = "";
  showInput.value = false;
}

// Focus input when shown
watch(showInput, async (value) => {
  if (value) {
    await nextTick();
    const input = tagInputRef.value?.$el?.querySelector("input");
    input?.focus();
  }
});

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
