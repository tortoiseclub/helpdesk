<template>
  <Popover placement="bottom-start">
    <template #target="{ togglePopover }">
      <Button @click="handleOpen(togglePopover)">
        <template #prefix>
          <LucideTag class="h-4 w-4" />
        </template>
        Tags
        <template v-if="selectedTags.length > 0" #suffix>
          <span
            class="flex h-5 w-5 items-center justify-center rounded-[5px] bg-surface-white pt-px text-xs font-medium text-ink-gray-8 shadow-sm"
          >
            {{ selectedTags.length }}
          </span>
        </template>
      </Button>
    </template>

    <template #body="{ close }">
      <div class="min-w-72 rounded-lg border border-gray-100 bg-white shadow-xl">
        <div class="p-3">
          <!-- Search tags -->
          <FormControl
            v-model="searchQuery"
            type="text"
            placeholder="Search tags..."
          >
            <template #prefix>
              <LucideSearch class="h-4 w-4 text-ink-gray-5" />
            </template>
          </FormControl>

          <!-- Tag list -->
          <div class="mt-3 space-y-1 max-h-64 overflow-y-auto">
            <div v-if="tagsResource.loading" class="text-center py-4 text-ink-gray-5">
              <LucideLoader2 class="h-4 w-4 animate-spin inline mr-2" />
              Loading tags...
            </div>
            <div
              v-else-if="filteredTags.length === 0"
              class="text-center py-4 text-ink-gray-5"
            >
              {{ searchQuery ? 'No matching tags' : 'No tags available' }}
            </div>
            <div
              v-else
              v-for="tag in filteredTags"
              :key="tag"
              class="flex items-center gap-2 cursor-pointer hover:bg-surface-gray-1 p-2 rounded transition-colors"
              @click="toggleTag(tag)"
            >
              <input
                type="checkbox"
                :checked="selectedTags.includes(tag)"
                class="rounded border-outline-gray-3"
                @click.stop
                @change="toggleTag(tag)"
              />
              <span class="text-sm text-ink-gray-8">{{ tag }}</span>
            </div>
          </div>

          <!-- Actions -->
          <div class="mt-3 pt-3 border-t flex justify-between gap-2">
            <Button
              variant="ghost"
              label="Clear"
              :disabled="selectedTags.length === 0"
              @click="clearTags(close)"
            />
            <Button
              variant="solid"
              label="Apply"
              @click="applyFilter(close)"
            />
          </div>
        </div>
      </div>
    </template>
  </Popover>
</template>

<script setup lang="ts">
import { Button, FormControl, Popover, createResource } from "frappe-ui";
import { computed, inject, ref, watch } from "vue";
import LucideSearch from "~icons/lucide/search";
import LucideTag from "~icons/lucide/tag";
import LucideLoader2 from "~icons/lucide/loader-2";

const listViewData = inject("listViewData") as any;
const listViewActions = inject("listViewActions") as any;

const selectedTags = ref<string[]>([]);
const searchQuery = ref("");

// Resource to get all available tags
const tagsResource = createResource({
  url: "frappe.desk.doctype.tag.tag.get_tags",
  transform: (data: string[]) => data || [],
});

function fetchTags() {
  tagsResource.submit({
    doctype: "HD Ticket",
    txt: "",
  });
}

const allTags = computed(() => tagsResource.data || []);

const filteredTags = computed(() => {
  if (!searchQuery.value) {
    return allTags.value;
  }
  const query = searchQuery.value.toLowerCase();
  return allTags.value.filter((tag: string) =>
    tag.toLowerCase().includes(query)
  );
});

function handleOpen(togglePopover: () => void) {
  fetchTags();
  togglePopover();
}

function toggleTag(tag: string) {
  const index = selectedTags.value.indexOf(tag);
  if (index > -1) {
    selectedTags.value.splice(index, 1);
  } else {
    selectedTags.value.push(tag);
  }
}

function clearTags(close: () => void) {
  selectedTags.value = [];
  applyFilter(close);
}

function applyFilter(close: () => void) {
  if (!listViewData || !listViewActions) {
    close();
    return;
  }

  const currentFilters = { ...listViewData.list.params?.filters };

  if (selectedTags.value.length === 0) {
    // Remove tag filter
    delete currentFilters["_user_tags"];
  } else if (selectedTags.value.length === 1) {
    // Single tag - use LIKE
    currentFilters["_user_tags"] = ["LIKE", `%${selectedTags.value[0]}%`];
  } else {
    // Multiple tags - we need to match any of them
    // Build a regex-like pattern: %tag1% OR %tag2%
    // For Frappe, we use multiple LIKE conditions
    // Since the filter system doesn't support OR, we'll use a workaround
    // by matching the first tag (limitation of current filter system)
    // TODO: Implement proper OR filtering when backend supports it
    const tagPattern = selectedTags.value.map(t => `%${t}%`).join(",");
    currentFilters["_user_tags"] = ["LIKE", `%${selectedTags.value[0]}%`];
  }

  listViewActions.applyFilters(currentFilters);
  close();
}

// Sync selected tags with current filters
watch(
  () => listViewData?.list?.params?.filters?._user_tags,
  (tagFilter) => {
    if (!tagFilter) {
      selectedTags.value = [];
      return;
    }
    // Extract tag from LIKE filter
    if (Array.isArray(tagFilter) && tagFilter[0] === "LIKE") {
      const value = tagFilter[1].replace(/%/g, "");
      if (value && !selectedTags.value.includes(value)) {
        selectedTags.value = [value];
      }
    }
  },
  { immediate: true }
);
</script>
