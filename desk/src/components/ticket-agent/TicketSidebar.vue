<template>
  <Resizer class="flex flex-col justify-between border-l" side="right">
    <TabButtons
      :buttons="visibleTabs"
      v-model="currentTab"
      class="tab-buttons mb-1 px-5 mt-3.5"
    />
    <div class="flex-1 overflow-y-auto">
      <TicketDetailsTab v-if="currentTab === 'details'" />
      <TicketContactTab v-else-if="currentTab === 'contact'" />
      <TortoiseTab v-else-if="currentTab === 'tortoise'" />
    </div>
  </Resizer>
</template>

<script setup lang="ts">
import { createResource, TabButtons } from "frappe-ui";
import { computed, onMounted, ref } from "vue";
import Resizer from "../Resizer.vue";
import TicketContactTab from "./TicketContactTab.vue";
import TicketDetailsTab from "./TicketDetailsTab.vue";
import TortoiseTab from "./TortoiseTab.vue";

const currentTab = ref("details");

// We keep the tab visible; the tab panel handles "not configured" state.
// Still load status here so it's fetched on ticket load (not only when tab opens).
const integrationStatus = createResource({
  url: "helpdesk.api.external_integration.check_integration_status",
  params: { app_name: "tortoise" },
  auto: true,
});

onMounted(() => {
  // Some builds don't trigger auto fetch if the resource is GC'd / unused.
  // Keeping it as a const + forcing reload makes the request deterministic.
  integrationStatus.reload();
});

const tabs = [
  {
    label: "Details",
    value: "details",
  },
  {
    label: "Contact",
    value: "contact",
  },
  {
    label: "Tortoise",
    value: "tortoise",
  },
];

const visibleTabs = computed(() => {
  // Touch reactive fields so this stays alive in the component.
  void integrationStatus.loading;
  void integrationStatus.data;
  return tabs;
});
</script>

<style>
.tab-buttons div,
.tab-buttons button {
  width: 100%;
  flex: 1;
}
</style>
