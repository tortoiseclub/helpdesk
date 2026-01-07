<template>
  <Dialog
    v-model="show"
    :options="{
      title: 'Add Tags to Tickets',
      size: 'md',
    }"
  >
    <template #body-content>
      <div class="space-y-4">
        <div>
          <p class="text-sm text-ink-gray-7 mb-4">
            Add tags to {{ selectedCount }} selected
            {{ selectedCount === 1 ? 'ticket' : 'tickets' }}
          </p>
        </div>

        <!-- Tag selection -->
        <div>
          <label class="text-sm font-medium text-ink-gray-8 mb-2 block">
            Select Tags
          </label>
          <Autocomplete
            :options="tagOptionsWithCreate"
            placeholder="Search or create tags..."
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

        <!-- Selected tags display -->
        <div v-if="tagsToAdd.length > 0">
          <label class="text-sm font-medium text-ink-gray-8 mb-2 block">
            Tags to Add
          </label>
          <div class="flex flex-wrap gap-2 p-3 bg-surface-gray-1 rounded">
            <Badge
              v-for="tag in tagsToAdd"
              :key="tag"
              :label="tag"
              theme="gray"
            >
              <template #suffix>
                <button
                  class="ml-1 hover:text-ink-gray-9"
                  @click="removeTagFromList(tag)"
                >
                  <LucideX class="size-3" />
                </button>
              </template>
            </Badge>
          </div>
        </div>

        <!-- Error message -->
        <div v-if="error" class="text-sm text-red-600">
          {{ error }}
        </div>
      </div>
    </template>

    <template #actions>
      <Button
        variant="ghost"
        label="Cancel"
        @click="cancel"
      />
      <Button
        variant="solid"
        label="Add Tags"
        :loading="loading"
        :disabled="tagsToAdd.length === 0"
        @click="addTags"
      />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { Autocomplete, Badge, Button, Dialog, toast } from "frappe-ui";
import { computed, ref, watch } from "vue";
import LucideX from "~icons/lucide/x";
import LucidePlus from "~icons/lucide/plus";
import LucideSearch from "~icons/lucide/search";
import LucideTag from "~icons/lucide/tag";
import { createResource } from "frappe-ui";

const props = defineProps<{
  modelValue: boolean;
  ticketIds: string[];
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  success: [];
}>();

const show = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

const selectedCount = computed(() => props.ticketIds.length);
const tagsToAdd = ref<string[]>([]);
const searchQuery = ref("");
const loading = ref(false);
const error = ref("");

// Resource to get tag suggestions
const tagSuggestionsResource = createResource({
  url: "frappe.desk.doctype.tag.tag.get_tags",
  transform: (data: string[]) =>
    (data || []).map((tag) => ({
      label: tag,
      value: tag,
    })),
});

// Filtered suggestions (excluding already selected tags)
const tagSuggestions = computed(() => {
  const suggestions = tagSuggestionsResource.data || [];
  return suggestions.filter((s) => !tagsToAdd.value.includes(s.value));
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
  const alreadySelected = tagsToAdd.value.some((t) => t.toLowerCase() === queryLower);
  
  // If no exact match and not already selected, add "Create" option
  if (!exactMatch && !alreadySelected) {
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
  if (tagValue && !tagsToAdd.value.includes(tagValue)) {
    tagsToAdd.value.push(tagValue);
  }
}

// Resource to add tags in bulk
const bulkAddResource = createResource({
  url: "frappe.desk.doctype.tag.tag.add_tags",
  onSuccess: () => {
    loading.value = false;
    toast.success(
      `Successfully added ${tagsToAdd.value.length} tag(s) to ${selectedCount.value} ticket(s)`
    );
    emit("success");
    cancel();
  },
  onError: (err) => {
    loading.value = false;
    error.value = err.message || "Failed to add tags";
    toast.error(error.value);
  },
});

function removeTagFromList(tag: string) {
  tagsToAdd.value = tagsToAdd.value.filter((t) => t !== tag);
}

function addTags() {
  if (tagsToAdd.value.length === 0) {
    error.value = "Please select at least one tag";
    return;
  }

  loading.value = true;
  error.value = "";

  bulkAddResource.submit({
    tags: JSON.stringify(tagsToAdd.value),
    dt: "HD Ticket",
    docs: JSON.stringify(props.ticketIds),
  });
}

function cancel() {
  show.value = false;
  tagsToAdd.value = [];
  searchQuery.value = "";
  error.value = "";
}

// Reset when dialog closes, fetch tags when opens
watch(show, (value) => {
  if (value) {
    // Fetch initial tags when modal opens
    fetchTags();
  } else {
    tagsToAdd.value = [];
    searchQuery.value = "";
    error.value = "";
  }
});
</script>

