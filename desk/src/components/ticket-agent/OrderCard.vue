<template>
  <div
    class="border border-outline-gray-2 rounded-lg overflow-hidden cursor-pointer hover:border-outline-gray-3 transition-colors"
    @click="$emit('click')"
  >
    <!-- Order Header -->
    <div class="p-3 bg-surface-white">
      <div class="flex items-start gap-3">
        <!-- Product Image -->
        <img
          v-if="primaryProduct?.product?.image_url"
          :src="primaryProduct.product.image_url"
          :alt="primaryProduct.product.short_name"
          class="size-12 object-contain rounded bg-surface-gray-1"
        />
        <div v-else class="size-12 bg-surface-gray-1 rounded flex items-center justify-center">
          <LucidePackage class="size-6 text-ink-gray-4" />
        </div>

        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-ink-gray-8 truncate">
            {{ primaryProduct?.product?.short_name || "Unknown Product" }}
          </p>
          <div class="flex items-center gap-2 mt-1">
            <span
              :class="statusClass"
              class="px-1.5 py-0.5 text-xs rounded font-medium"
            >
              {{ order.status }}
            </span>
            <span class="text-xs text-ink-gray-5">
              {{ formatDate(order.created_at) }}
            </span>
          </div>
        </div>

        <!-- Expand Icon -->
        <LucideChevronDown
          class="size-4 text-ink-gray-5 transition-transform"
          :class="{ 'rotate-180': expanded }"
        />
      </div>
    </div>

    <!-- Expanded Details -->
    <div v-if="expanded" class="border-t border-outline-gray-2 bg-surface-gray-1 p-3">
      <!-- Products List -->
      <div class="mb-3">
        <p class="text-xs font-medium text-ink-gray-6 mb-2">Products</p>
        <div class="space-y-2">
          <div
            v-for="product in order.products"
            :key="product.id"
            class="flex items-center justify-between text-sm"
          >
            <span class="text-ink-gray-7 truncate flex-1">
              {{ product.product?.short_name || product.product?.name }}
            </span>
            <span class="text-ink-gray-8 font-medium ml-2">
              {{ formatCurrency(product.price) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Order Summary -->
      <div v-if="order.ui_helpers?.summary" class="border-t border-outline-gray-2 pt-3 space-y-2">
        <div class="flex justify-between text-sm">
          <span class="text-ink-gray-5">Device Cost</span>
          <span class="text-ink-gray-8">{{ formatCurrency(order.ui_helpers.summary.device_cost) }}</span>
        </div>
        <div class="flex justify-between text-sm">
          <span class="text-ink-gray-5">Tenure</span>
          <span class="text-ink-gray-8">{{ order.ui_helpers.summary.tenure }} months</span>
        </div>
        <div class="flex justify-between text-sm">
          <span class="text-ink-gray-5">Monthly Deduction</span>
          <span class="text-ink-gray-8">{{ formatCurrency(order.ui_helpers.summary.monthly_salary_deduction) }}</span>
        </div>
        <div v-if="order.ui_helpers.summary.total_savings" class="flex justify-between text-sm">
          <span class="text-ink-gray-5">Total Savings</span>
          <span class="text-green-600 font-medium">{{ formatCurrency(order.ui_helpers.summary.total_savings) }}</span>
        </div>
      </div>

      <!-- Order Details -->
      <div class="border-t border-outline-gray-2 pt-3 mt-3 space-y-1">
        <div class="flex justify-between text-xs">
          <span class="text-ink-gray-5">Order ID</span>
          <span class="text-ink-gray-7 font-mono">{{ order.order_id }}</span>
        </div>
        <div class="flex justify-between text-xs">
          <span class="text-ink-gray-5">Request ID</span>
          <span class="text-ink-gray-7 font-mono">{{ order.id }}</span>
        </div>
      </div>

      <!-- Order Flags -->
      <div v-if="order.flags" class="border-t border-outline-gray-2 pt-3 mt-3">
        <p class="text-xs font-medium text-ink-gray-6 mb-2">Status</p>
        <div class="flex flex-wrap gap-1.5">
          <span
            v-for="(value, key) in orderFlags"
            :key="key"
            class="px-1.5 py-0.5 text-xs rounded"
            :class="value ? 'bg-green-100 text-green-700' : 'bg-surface-gray-2 text-ink-gray-5'"
          >
            {{ formatFlagLabel(key as string) }}
          </span>
        </div>
      </div>

      <!-- Shipping Address -->
      <div v-if="order.order?.shipping_address" class="border-t border-outline-gray-2 pt-3 mt-3">
        <p class="text-xs font-medium text-ink-gray-6 mb-1">Shipping Address</p>
        <p class="text-xs text-ink-gray-7">{{ order.order.shipping_address }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import dayjs from "dayjs";
import { computed } from "vue";
import LucideChevronDown from "~icons/lucide/chevron-down";
import LucidePackage from "~icons/lucide/package";

interface Product {
  id: number;
  item_type: string;
  price: number;
  product: {
    id: string;
    name: string;
    short_name: string;
    image_url: string;
    device_type: string;
  };
  type: string;
}

interface Order {
  id: string;
  status: string;
  order_id: string;
  created_at: string;
  products: Product[];
  terms?: any;
  ui_helpers?: {
    summary?: {
      device_cost: number;
      tenure: number;
      monthly_salary_deduction: number;
      total_savings: number;
    };
  };
  flags?: Record<string, boolean>;
  order?: {
    shipping_address?: string;
  };
}

const props = defineProps<{
  order: Order;
  expanded: boolean;
}>();

defineEmits<{
  click: [];
}>();

const primaryProduct = computed(() => {
  return props.order.products?.find((p) => p.item_type === "base" || p.type === "base");
});

const statusClass = computed(() => {
  const status = props.order.status?.toLowerCase();
  switch (status) {
    case "approved":
      return "bg-green-100 text-green-700";
    case "rejected":
      return "bg-red-100 text-red-700";
    case "pending":
      return "bg-yellow-100 text-yellow-700";
    default:
      return "bg-surface-gray-2 text-ink-gray-6";
  }
});

const orderFlags = computed(() => {
  if (!props.order.flags) return {};
  // Filter to show only relevant flags
  const relevantFlags = [
    "is_order_confirmed",
    "is_order_shipped",
    "is_order_delivered",
    "is_asset_assigned",
  ];
  return Object.fromEntries(
    Object.entries(props.order.flags).filter(([key]) => relevantFlags.includes(key))
  );
});

function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  return dayjs(dateStr).format("DD MMM YYYY");
}

function formatCurrency(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return "N/A";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatFlagLabel(key: string): string {
  return key
    .replace(/^is_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (l) => l.toUpperCase());
}
</script>

