<template>
  <div class="flex flex-1 flex-col px-5 py-4">
    <!-- Integration disabled / not configured -->
    <div
      v-if="!integrationReady && !integrationStatus.loading"
      class="flex flex-col items-center justify-center py-8 text-center"
    >
      <LucidePackage class="size-8 text-ink-gray-4 mb-2" />
      <p class="text-sm text-ink-gray-6">Tortoise integration is not configured</p>
      <p class="text-xs text-ink-gray-5 mt-1">
        Configure it in <span class="font-medium">HD External Integration Settings</span>
      </p>
    </div>

    <!-- Loading State -->
    <div
      v-else-if="integrationStatus.loading || employeeData.loading"
      class="flex items-center justify-center py-8"
    >
      <LoadingIndicator class="size-6 text-ink-gray-5" />
    </div>

    <!-- Error State -->
    <div
      v-else-if="employeeData.data?.error"
      class="flex flex-col items-center justify-center py-8 text-center"
    >
      <LucideAlertCircle class="size-8 text-ink-gray-4 mb-2" />
      <p class="text-sm text-ink-gray-6">{{ employeeData.data.error }}</p>
    </div>

    <!-- Employee Data -->
    <div v-else-if="employee" class="space-y-4">
      <!-- Employee Header -->
      <div class="flex items-center gap-3 pb-3 border-b border-outline-gray-2">
        <Avatar :label="employeeName" size="xl" />
        <div class="flex-1 min-w-0">
          <p class="text-base font-medium text-ink-gray-9 truncate">
            {{ employeeName }}
          </p>
          <p class="text-sm text-ink-gray-6 truncate">{{ employee.designation }}</p>
          <p class="text-xs text-ink-gray-5">ID: {{ employee.employee_id }}</p>
        </div>
      </div>

      <!-- Quick Stats -->
      <div class="grid grid-cols-2 gap-3">
        <div class="bg-surface-gray-1 rounded-lg p-3">
          <p class="text-xs text-ink-gray-5 mb-1">Device Allowance</p>
          <p class="text-sm font-medium text-ink-gray-8">
            {{ formatCurrency(employee.device_allowance_limit) }}
          </p>
        </div>
        <div class="bg-surface-gray-1 rounded-lg p-3">
          <p class="text-xs text-ink-gray-5 mb-1">Consumed</p>
          <p class="text-sm font-medium text-ink-gray-8">
            {{ formatCurrency(employee.consumed_salary_sacrifice_limit) }}
          </p>
        </div>
      </div>

      <!-- Employee Band -->
      <div v-if="employee.employee_band" class="text-sm">
        <span class="text-ink-gray-5">Band: </span>
        <span class="text-ink-gray-8 font-medium">{{ employee.employee_band }}</span>
      </div>

      <!-- Orders Section -->
      <div v-if="orders.length > 0" class="border-t border-outline-gray-2 pt-4">
        <p class="text-base font-medium text-ink-gray-8 mb-3">Orders</p>
        <div class="space-y-3">
          <OrderCard
            v-for="order in orders"
            :key="order.id"
            :order="order"
            @click="toggleOrderExpand(order.id)"
            :expanded="expandedOrderId === order.id"
          />
        </div>
      </div>

      <!-- No Orders -->
      <div
        v-else
        class="border-t border-outline-gray-2 pt-4 text-center text-ink-gray-5 text-sm"
      >
        No orders found
      </div>
    </div>

    <!-- No Data State -->
    <div
      v-else
      class="flex flex-col items-center justify-center py-8 text-center"
    >
      <LucidePackage class="size-8 text-ink-gray-4 mb-2" />
      <p class="text-sm text-ink-gray-6">No employee data available</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { TicketSymbol } from "@/types";
import { Avatar, createResource, LoadingIndicator } from "frappe-ui";
import { computed, inject, onMounted, ref, watch } from "vue";
import LucideAlertCircle from "~icons/lucide/alert-circle";
import LucidePackage from "~icons/lucide/package";
import OrderCard from "./OrderCard.vue";

const ticket = inject(TicketSymbol);

const expandedOrderId = ref<string | null>(null);

const APP_NAME = "tortoise";

const integrationStatus = createResource({
  url: "helpdesk.api.external_integration.check_integration_status",
  params: { app_name: APP_NAME },
  auto: true,
});

onMounted(() => {
  integrationStatus.reload();
});

const employeeData = createResource({
  url: "helpdesk.api.external_integration.get_employee_data",
  makeParams: () => ({
    ticket_id: ticket?.value?.name,
    app_name: APP_NAME,
  }),
});

const integrationReady = computed(() => {
  return Boolean(integrationStatus.data?.enabled && integrationStatus.data?.configured);
});

// Fetch data when ticket changes
watch(
  () => [ticket?.value?.name, integrationReady.value],
  (ticketId) => {
    if (ticketId && integrationReady.value) {
      employeeData.reload();
    }
  },
  { immediate: true }
);

const employee = computed(() => employeeData.data?.data || null);

const employeeName = computed(() => {
  if (!employee.value) return "";
  const firstName = employee.value.first_name || "";
  const lastName = employee.value.last_name || "";
  return `${firstName} ${lastName}`.trim();
});

const orders = computed(() => {
  if (!employee.value?.claimed_benefits) return [];
  return employee.value.claimed_benefits;
});

function formatCurrency(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return "N/A";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function toggleOrderExpand(orderId: string) {
  expandedOrderId.value = expandedOrderId.value === orderId ? null : orderId;
}
</script>

