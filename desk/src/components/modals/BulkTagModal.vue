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
            v-model="selectedTag"
            :options="tagSuggestions"
            placeholder="Type to search tags..."
            @update:modelValue="addTagToList"
          >
            <template #target="{ togglePopover }">
              <FormControl
                v-model="tagInput"
                type="text"
                placeholder="Type to search or create tags..."
                @input="searchTags"
                @focus="togglePopover"
                @keydown.enter.prevent="addTagFromInput"
              />
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
import { Autocomplete, Badge, Button, Dialog, FormControl, toast } from "frappe-ui";
import { computed, ref, watch } from "vue";
import LucideX from "~icons/lucide/x";
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
const tagInput = ref("");
const selectedTag = ref("");
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

const tagSuggestions = computed(() => {
  const suggestions = tagSuggestionsResource.data || [];
  // Filter out already selected tags
  return suggestions.filter((s) => !tagsToAdd.value.includes(s.value));
});

function fetchTags(searchText = "") {
  tagSuggestionsResource.submit({
    doctype: "HD Ticket",
    txt: searchText,
  });
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

function searchTags() {
  fetchTags(tagInput.value.trim());
}

function addTagToList(value: string | { label: string; value: string }) {
  // Extract the actual tag string from selection
  const tagValue = typeof value === "string" ? value : value?.value;
  if (tagValue && !tagsToAdd.value.includes(tagValue)) {
    tagsToAdd.value.push(tagValue);
    tagInput.value = "";
    selectedTag.value = "";
  }
}

function addTagFromInput() {
  const tag = tagInput.value.trim();
  if (tag && !tagsToAdd.value.includes(tag)) {
    tagsToAdd.value.push(tag);
    tagInput.value = "";
  }
}

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
  tagInput.value = "";
  selectedTag.value = "";
  error.value = "";
}

// Reset when dialog closes, fetch tags when opens
watch(show, (value) => {
  if (value) {
    // Fetch initial tags when modal opens
    fetchTags();
  } else {
    tagsToAdd.value = [];
    tagInput.value = "";
    selectedTag.value = "";
    error.value = "";
  }
});
</script>

