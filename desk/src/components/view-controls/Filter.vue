<template>
  <div class="flex items-center gap-1">
    <Popover placement="bottom-end">
      <template #target="{ togglePopover, close }">
        <div class="flex items-center w-fit">
          <Button
            :label="'Filter'"
            :class="hasActiveFilters ? 'rounded-r-none' : ''"
            @click="togglePopover"
          >
            <template #prefix><FilterIcon class="h-4" /></template>
            <template v-if="hasActiveFilters" #suffix>
              <span
                class="flex h-5 w-5 items-center justify-center rounded-[5px] bg-surface-white pt-px text-xs font-medium text-ink-gray-8 shadow-sm"
              >
                {{ filterCount }}
              </span>
            </template>
          </Button>
          <Tooltip v-if="hasActiveFilters" :text="'Clear all Filter'">
            <div>
              <Button
                class="rounded-l-none border-l"
                icon="x"
                @click.stop="clearfilter(close)"
              />
            </div>
          </Tooltip>
        </div>
      </template>
      <template #body="{ close }">
        <div class="my-2 rounded-lg border border-gray-100 bg-white shadow-xl">
          <div class="min-w-72 p-2 sm:min-w-[400px]">
            <!-- Advanced filter indicator -->
            <div
              v-if="isAdvancedMode"
              class="mb-3 flex items-center justify-between px-3 py-2 bg-surface-gray-2 rounded-md"
            >
              <div class="flex items-center gap-2 text-sm text-ink-gray-7">
                <FeatherIcon name="git-branch" class="h-4 w-4" />
                <span>{{ __('Advanced filters active') }}</span>
                <span class="text-ink-gray-5">({{ advancedFilterCount }})</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                :label="__('Edit')"
                @click="openAdvancedFilter(); close()"
              />
            </div>

            <!-- Simple filters (only show when not in advanced mode) -->
            <template v-if="!isAdvancedMode">
              <div
                v-if="filters?.size"
                v-for="(f, i) in filters"
                :key="i"
                id="filter-list"
                class="mb-4 sm:mb-3"
              >
                <div v-if="isMobileView" class="flex flex-col gap-2">
                  <div class="-mb-2 flex w-full items-center justify-between">
                    <div class="text-base text-gray-600">
                      {{ i == 0 ? "Where" : "And" }}
                    </div>
                    <Button
                      class="flex"
                      variant="ghost"
                      icon="x"
                      @click="removeFilter(i)"
                    />
                  </div>
                  <div id="fieldname" class="w-full">
                    <Autocomplete
                      v-model="f.field.fieldname"
                      :options="filterableFields.data"
                      @update:modelValue="(e) => updateFilter(e, i)"
                      :placeholder="'First Name'"
                    />
                  </div>
                  <div id="operator">
                    <FormControl
                      type="select"
                      v-model="f.operator"
                      @change="(e) => updateOperator(e, f)"
                      :options="getOperators(f.field.fieldtype, f.field.fieldname)"
                      :placeholder="'Equals'"
                    />
                  </div>
                  <div id="value" class="w-full">
                    <component
                      :is="getValueControl(f)"
                      v-model="f.value"
                      @change="(v) => updateValue(v, f)"
                      :placeholder="'John Doe'"
                    />
                  </div>
                </div>
                <div v-else class="flex items-center justify-between gap-2">
                  <div class="flex items-center gap-2 flex-1">
                    <div class="w-13 pl-2 text-end text-base text-gray-600">
                      {{ i == 0 ? "Where" : "And" }}
                    </div>
                    <div id="fieldname" class="!min-w-[140px]">
                      <Autocomplete
                        v-model="f.field.fieldname"
                        :options="filterableFields.data"
                        @update:modelValue="(e) => updateFilter(e, i)"
                        :placeholder="'First Name'"
                      />
                    </div>
                    <div id="operator">
                      <FormControl
                        type="select"
                        v-model="f.operator"
                        @change="(e) => updateOperator(e, f)"
                        :options="
                          getOperators(f.field.fieldtype, f.field.fieldname)
                        "
                        :placeholder="'Equals'"
                      />
                    </div>
                    <div id="value" class="!min-w-[140px] flex-1">
                      <component
                        :is="getValueControl(f)"
                        v-model="f.value"
                        @change="(v) => updateValue(v, f)"
                        :placeholder="'John Doe'"
                      />
                    </div>
                  </div>
                  <Button
                    class="flex"
                    variant="ghost"
                    icon="x"
                    @click="removeFilter(i)"
                  />
                </div>
              </div>
              <div
                v-if="!filters?.size"
                class="mb-3 flex h-7 items-center px-3 text-sm text-gray-600"
              >
                {{ "Empty - Choose a field to filter by" }}
              </div>
              <div class="flex items-center justify-between gap-2">
                <Autocomplete
                  :options="filterableFields.data"
                  @update:modelValue="(e) => setfilter(e)"
                  :placeholder="'First name'"
                >
                  <template #target="{ togglePopover }">
                    <Button
                      class="!text-gray-600"
                      variant="ghost"
                      @click="togglePopover()"
                      :label="'Add Filter'"
                    >
                      <template #prefix>
                        <FeatherIcon name="plus" class="h-4" />
                      </template>
                    </Button>
                  </template>
                </Autocomplete>
                <Button
                  v-if="filters?.size"
                  class="!text-gray-600"
                  variant="ghost"
                  :label="'Clear all Filter'"
                  @click="clearfilter(close)"
                />
              </div>
            </template>

            <!-- Divider and Advanced Filter button -->
            <div class="border-t border-gray-200 mt-3 pt-3">
              <Button
                class="w-full !text-gray-600"
                variant="ghost"
                :label="isAdvancedMode ? __('Switch to Simple Filter') : __('Advanced Filter (AND/OR)')"
                @click="isAdvancedMode ? switchToSimpleMode(close) : openAdvancedFilter(); close()"
              >
                <template #prefix>
                  <FeatherIcon :name="isAdvancedMode ? 'filter' : 'git-branch'" class="h-4" />
                </template>
              </Button>
            </div>
          </div>
        </div>
      </template>
    </Popover>

    <!-- Advanced Filter Dialog using CFConditions -->
    <Dialog
      v-model="showAdvancedFilter"
      :options="{
        size: '4xl',
        title: __('Advanced Filter'),
      }"
    >
      <template #body-content>
        <div class="flex flex-col gap-4">
          <div class="text-sm text-ink-gray-6">
            {{ __('Create complex filter conditions with AND/OR logic and nested groups.') }}
          </div>

          <!-- Conditions UI - same as Assignment Rules -->
          <div class="min-h-[150px]">
            <CFConditions
              v-if="advancedConditions.length > 0"
              :conditions="advancedConditions"
              :level="0"
              :disableAddCondition="false"
            />
            <div
              v-else
              class="flex p-4 items-center cursor-pointer justify-center gap-2 text-sm border border-gray-300 text-gray-600 rounded-md"
              @click="addFirstCondition"
            >
              <FeatherIcon name="plus" class="h-4" />
              {{ __('Add a condition') }}
            </div>
          </div>

          <!-- Add condition dropdown -->
          <div class="flex items-center justify-between">
            <Dropdown
              v-if="advancedConditions.length > 0"
              v-slot="{ open }"
              :options="conditionDropdownOptions"
            >
              <Button
                :icon-right="open ? 'chevron-up' : 'chevron-down'"
                :label="__('Add condition')"
              />
            </Dropdown>
            <div v-else></div>

            <div class="flex gap-2">
              <Button
                v-if="advancedConditions.length > 0"
                variant="subtle"
                :label="__('Clear All')"
                @click="clearAdvancedConditions"
              />
              <Button
                variant="solid"
                theme="gray"
                :label="__('Apply Filters')"
                @click="applyAdvancedFilters"
              />
            </div>
          </div>
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { Link, StarRating } from "@/components";
import FilterIcon from "@/components/icons/FilterIcon.vue";
import CFConditions from "@/components/conditions-filter/CFConditions.vue";
import { useScreenSize } from "@/composables/screen";
import { validateConditions } from "@/utils";
import {
  Autocomplete,
  Button,
  DatePicker,
  DateRangePicker,
  DateTimePicker,
  Dialog,
  Dropdown,
  FeatherIcon,
  FormControl,
  Popover,
  Tooltip,
} from "frappe-ui";
import { computed, h, inject, ref, onMounted, watch } from "vue";
import { __ } from "@/translation";

const props = defineProps({
  default_filters: {
    type: Object,
    required: false,
    default: {},
  },
});

const { isMobileView } = useScreenSize();

const typeCheck = ["Check"];
const typeLink = ["Link", "Dynamic Link"];
const typeNumber = ["Float", "Int", "Currency", "Percent"];
const typeSelect = ["Select"];
const typeString = ["Data", "Long Text", "Small Text", "Text Editor", "Text"];
const typeDate = ["Date", "Datetime"];
const typeRating = ["Rating"];

const listViewData = inject("listViewData");
const listViewActions = inject("listViewActions");
const { list, filterableFields } = listViewData;

// Advanced filter state - array format like Assignment Rules
const showAdvancedFilter = ref(false);
const advancedConditions = ref([]);
const isAdvancedMode = ref(false);

// Sync advanced filter state from parent on mount
onMounted(() => {
  syncAdvancedFiltersFromParent();
});

// Watch for changes in the list params to detect when advanced filters change
watch(
  () => list?.params?.filters,
  () => {
    syncAdvancedFiltersFromParent();
  },
  { deep: true }
);

function syncAdvancedFiltersFromParent() {
  if (listViewActions?.getAdvancedFilters) {
    const parentAdvancedFilters = listViewActions.getAdvancedFilters();
    if (parentAdvancedFilters && parentAdvancedFilters.length > 0) {
      advancedConditions.value = parentAdvancedFilters;
      isAdvancedMode.value = true;
    } else {
      // Check if current filters have _conditions key
      const currentFilters = list?.params?.filters;
      if (currentFilters?._conditions && currentFilters._conditions.length > 0) {
        advancedConditions.value = currentFilters._conditions;
        isAdvancedMode.value = true;
      }
    }
  }
}

// Count conditions in advanced filter (not counting conjunctions)
function countConditions(conditions) {
  if (!conditions || conditions.length === 0) return 0;
  let count = 0;
  for (const item of conditions) {
    if (typeof item === 'string') continue; // Skip 'and'/'or'
    if (Array.isArray(item)) {
      if (isSimpleCondition(item)) {
        count++;
      } else {
        count += countConditions(item);
      }
    }
  }
  return count;
}

function isSimpleCondition(arr) {
  return (
    arr.length === 3 &&
    typeof arr[0] === 'string' &&
    typeof arr[1] === 'string' &&
    arr[0] !== 'and' &&
    arr[0] !== 'or'
  );
}

// Check if we have active filters (either simple or advanced)
const hasActiveFilters = computed(() => {
  if (isAdvancedMode.value) {
    return advancedConditions.value.length > 0;
  }
  return filters.value?.size > 0;
});

// Get filter count for badge
const filterCount = computed(() => {
  if (isAdvancedMode.value) {
    return countConditions(advancedConditions.value);
  }
  return filters.value?.size || 0;
});

const advancedFilterCount = computed(() => {
  return countConditions(advancedConditions.value);
});

// Get current conjunction in the conditions
function getConjunction() {
  let conjunction = "and";
  advancedConditions.value.forEach((condition) => {
    if (typeof condition === "string") {
      conjunction = condition;
    }
  });
  return conjunction;
}

// Dropdown options for adding conditions
const conditionDropdownOptions = computed(() => [
  {
    label: __("Add condition"),
    onClick: () => {
      addCondition();
    },
  },
  {
    label: __("Add condition group"),
    onClick: () => {
      const conjunction = getConjunction();
      advancedConditions.value.push(conjunction, [[]]);
    },
  },
]);

function addFirstCondition() {
  advancedConditions.value.push(["", "", ""]);
}

function addCondition() {
  const isValid = validateConditions(advancedConditions.value);
  if (!isValid) {
    return;
  }
  const conjunction = getConjunction();
  advancedConditions.value.push(conjunction, ["", "", ""]);
}

function clearAdvancedConditions() {
  advancedConditions.value = [];
}

function applyAdvancedFilters() {
  // Validate that we have valid conditions
  if (advancedConditions.value.length > 0) {
    const isValid = validateConditions(advancedConditions.value);
    if (!isValid) {
      // Don't apply if invalid
      return;
    }
  }

  isAdvancedMode.value = advancedConditions.value.length > 0;
  
  if (advancedConditions.value.length > 0) {
    // Pass conditions to backend with special key
    listViewActions.applyFilters({
      _conditions: JSON.parse(JSON.stringify(advancedConditions.value)),
    });
  } else {
    listViewActions.applyFilters({});
  }
  
  showAdvancedFilter.value = false;
}

function openAdvancedFilter() {
  // If we have existing advanced conditions, use them
  // Otherwise start fresh
  if (!isAdvancedMode.value) {
    advancedConditions.value = [];
  }
  showAdvancedFilter.value = true;
}

function switchToSimpleMode(close) {
  isAdvancedMode.value = false;
  advancedConditions.value = [];
  // Clear all filters and apply
  listViewActions.applyFilters({});
  close && close();
}

const filters = computed(() => {
  if (!list) return new Set();
  let allFilters = list?.params?.filters || list.data?.params?.filters;
  if (!allFilters || !filterableFields.data) return new Set();
  
  // Skip if we're in advanced mode
  if (isAdvancedMode.value) return new Set();

  return convertFilters(filterableFields.data, allFilters);
});

function convertFilters(data, allFilters) {
  let f = [];
  for (let [key, value] of Object.entries(allFilters)) {
    // Skip internal keys
    if (key.startsWith('_')) continue;
    
    let field = data.find((f) => f.fieldname === key);
    if (typeof value !== "object" || !value) {
      value = ["=", value];
      if (field?.fieldtype === "Check") {
        value = ["equals", value[1] ? "Yes" : "No"];
      }
    }
    if (typeof value[1] === "number") {
      value[1] = value[1].toString();
    }
    if (field) {
      f.push({
        field,
        fieldname: key,
        operator: oppositeOperatorMap[value[0]],
        value: value[1],
      });
    }
  }
  return new Set(f);
}

function getOperators(fieldtype, fieldname) {
  let options = [];
  if (typeString.includes(fieldtype)) {
    options.push(
      ...[
        { label: "Equals", value: "equals" },
        { label: "Not Equals", value: "not equals" },
        { label: "Like", value: "like" },
        { label: "Not Like", value: "not like" },
        { label: "In", value: "in" },
        { label: "Not In", value: "not in" },
        { label: "Is", value: "is" },
      ]
    );
  }
  if (fieldname === "_assign") {
    // TODO: make equals and not equals work
    options = [
      { label: "Like", value: "like" },
      { label: "Not Like", value: "not like" },
      { label: "Is", value: "is" },
    ];
  }
  if (typeNumber.includes(fieldtype)) {
    options.push(
      ...[
        { label: "Equals", value: "equals" },
        { label: "Not Equals", value: "not equals" },
        { label: "Like", value: "like" },
        { label: "Not Like", value: "not like" },
        { label: "In", value: "in" },
        { label: "Not In", value: "not in" },
        { label: "Is", value: "is" },
        { label: "<", value: "<" },
        { label: ">", value: ">" },
        { label: "<=", value: "<=" },
        { label: ">=", value: ">=" },
      ]
    );
  }
  if (typeSelect.includes(fieldtype)) {
    options.push(
      ...[
        { label: "Equals", value: "equals" },
        { label: "Not Equals", value: "not equals" },
        { label: "In", value: "in" },
        { label: "Not In", value: "not in" },
        { label: "Is", value: "is" },
      ]
    );
  }
  if (typeLink.includes(fieldtype)) {
    options.push(
      ...[
        { label: "Equals", value: "equals" },
        { label: "Not Equals", value: "not equals" },
        { label: "Like", value: "like" },
        { label: "Not Like", value: "not like" },
        { label: "In", value: "in" },
        { label: "Not In", value: "not in" },
        { label: "Is", value: "is" },
      ]
    );
  }
  if (typeCheck.includes(fieldtype)) {
    options.push(...[{ label: "Equals", value: "equals" }]);
  }
  if (["Duration"].includes(fieldtype)) {
    options.push(
      ...[
        { label: "Like", value: "like" },
        { label: "Not Like", value: "not like" },
        { label: "In", value: "in" },
        { label: "Not In", value: "not in" },
        { label: "Is", value: "is" },
      ]
    );
  }
  if (typeDate.includes(fieldtype)) {
    options.push(
      ...[
        { label: "Equals", value: "equals" },
        { label: "Not Equals", value: "not equals" },
        { label: "Is", value: "is" },
        { label: ">", value: ">" },
        { label: "<", value: "<" },
        { label: ">=", value: ">=" },
        { label: "<=", value: "<=" },
        { label: "Between", value: "between" },
        { label: "Timespan", value: "timespan" },
      ]
    );
  }
  if (typeRating.includes(fieldtype)) {
    options.push(
      ...[
        { label: "Equals", value: "equals" },
        { label: "Not Equals", value: "not equals" },
        { label: "Is", value: "is" },
        { label: ">", value: ">" },
        { label: "<", value: "<" },
        { label: ">=", value: ">=" },
        { label: "<=", value: "<=" },
      ]
    );
  }
  return options;
}

function getValueControl(f) {
  const { field, operator } = f;
  const { fieldtype, options } = field;
  if (operator == "is") {
    return h(FormControl, {
      type: "select",
      options: [
        {
          label: "Set",
          value: "set",
        },
        {
          label: "Not Set",
          value: "not set",
        },
      ],
    });
  } else if (operator == "timespan") {
    return h(FormControl, {
      type: "select",
      options: timespanOptions,
    });
  } else if (["like", "not like", "in", "not in"].includes(operator)) {
    return h(FormControl, { type: "text" });
  } else if (typeSelect.includes(fieldtype) || typeCheck.includes(fieldtype)) {
    const _options =
      fieldtype == "Check" ? ["Yes", "No"] : getSelectOptions(options);
    return h(FormControl, {
      type: "select",
      options: _options.map((o) => ({
        label: o,
        value: o,
      })),
    });
  } else if (typeLink.includes(fieldtype)) {
    if (fieldtype == "Dynamic Link") {
      return h(FormControl, { type: "text" });
    }
    return h(Link, { class: "form-control", doctype: options, value: f.value });
  } else if (typeNumber.includes(fieldtype)) {
    return h(FormControl, { type: "number" });
  } else if (typeDate.includes(fieldtype) && operator == "between") {
    return h(DateRangePicker, { value: f.value, iconLeft: "" });
  } else if (typeDate.includes(fieldtype)) {
    return h(fieldtype == "Date" ? DatePicker : DateTimePicker, {
      value: f.value,
      iconLeft: "",
    });
  } else if (typeRating.includes(fieldtype)) {
    return h(StarRating, {
      rating: f.value || 0,
      static: false,
      class: "truncate",
      "onUpdate:modelValue": (v) => updateValue(v, f),
    });
  } else {
    return h(FormControl, { type: "text" });
  }
}

function getDefaultValue(field) {
  if (typeSelect.includes(field.fieldtype)) {
    return getSelectOptions(field.options)[0];
  }
  if (typeCheck.includes(field.fieldtype)) {
    return "Yes";
  }
  if (typeDate.includes(field.fieldtype)) {
    return null;
  }
  if (typeRating.includes(field.fieldtype)) {
    return 0;
  }
  return "";
}

function getDefaultOperator(fieldtype, fieldname = null) {
  if (fieldname === "_assign") {
    return "like";
  }
  if (typeSelect.includes(fieldtype)) {
    return "equals";
  }
  if (typeCheck.includes(fieldtype) || typeNumber.includes(fieldtype)) {
    return "equals";
  }
  if (typeDate.includes(fieldtype)) {
    return "between";
  }
  if (typeLink.includes(fieldtype)) {
    return "equals";
  }
  if (typeRating.includes(fieldtype)) {
    return "equals";
  }
  return "like";
}

function getSelectOptions(options) {
  return options.split("\n");
}

function setfilter(data) {
  if (!data) return;
  filters.value.add({
    field: {
      label: data.label,
      fieldname: data.value,
      fieldtype: data.fieldtype,
      options: data.options,
    },
    fieldname: data.value,
    operator: getDefaultOperator(data.fieldtype, data.fieldname),
    value: getDefaultValue(data),
  });
  apply();
}

function updateFilter(data, index) {
  filters.value.delete(Array.from(filters.value)[index]);
  filters.value.add({
    fieldname: data.value,
    operator: getDefaultOperator(data.fieldtype),
    value: getDefaultValue(data),
    field: {
      label: data.label,
      fieldname: data.value,
      fieldtype: data.fieldtype,
      options: data.options,
    },
  });
  apply();
}

function removeFilter(index) {
  filters.value.delete(Array.from(filters.value)[index]);
  apply();
}

function clearfilter(close) {
  // Clear both simple and advanced filters
  filters.value.clear();
  advancedConditions.value = [];
  isAdvancedMode.value = false;
  apply();
  close && close();
}

function updateValue(value, filter) {
  value = value.target ? value.target.value : value;
  if (filter.operator === "between") {
    filter.value = [value.split(",")[0], value.split(",")[1]];
  } else {
    filter.value = value;
  }
  apply();
}

function updateOperator(event, filter) {
  let oldOperatorValue = event.target._value;
  let newOperatorValue = event.target.value;
  filter.operator = event.target.value;
  if (!isSameTypeOperator(oldOperatorValue, newOperatorValue)) {
    filter.value = getDefaultValue(filter.field);
  }
  if (newOperatorValue === "is" || newOperatorValue === "is not") {
    filter.value = "set";
  }
  apply();
}

function isSameTypeOperator(oldOperator, newOperator) {
  let textOperators = [
    "equals",
    "not equals",
    "in",
    "not in",
    ">",
    "<",
    ">=",
    "<=",
  ];
  if (
    textOperators.includes(oldOperator) &&
    textOperators.includes(newOperator)
  )
    return true;
  return false;
}

function apply() {
  const _filters = [];
  filters.value.forEach((f) => {
    _filters.push({
      fieldname: f.fieldname,
      operator: f.operator,
      value: f.value,
      toBoolean: f.field.fieldtype === "Check",
    });
  });
  listViewActions.applyFilters(parseFilters(_filters));
}

function parseFilters(filters) {
  return filters.map(transformIn).reduce((p, c) => {
    if (["equals", "="].includes(c.operator)) {
      if (c.toBoolean) {
        p[c.fieldname] =
          c.value === "Yes" ? true : c.value === "No" ? false : c.value;
      } else {
        p[c.fieldname] = c.value;
      }
    } else {
      p[c.fieldname] = [operatorMap[c.operator.toLowerCase()], c.value];
    }
    return p;
  }, {});
}

function transformIn(f) {
  if (f.operator.includes("like") && !f.value.includes("%")) {
    f.value = `%${f.value}%`;
  }
  return f;
}

const operatorMap = {
  is: "is",
  "is not": "is not",
  in: "in",
  "not in": "not in",
  equals: "=",
  "not equals": "!=",
  yes: true,
  no: false,
  like: "LIKE",
  "not like": "NOT LIKE",
  ">": ">",
  "<": "<",
  ">=": ">=",
  "<=": "<=",
  between: "between",
  timespan: "timespan",
};

const oppositeOperatorMap = {
  is: "is",
  "=": "equals",
  "!=": "not equals",
  equals: "equals",
  "is not": "is not",
  true: "yes",
  false: "no",
  LIKE: "like",
  "NOT LIKE": "not like",
  in: "in",
  "not in": "not in",
  ">": ">",
  "<": "<",
  ">=": ">=",
  "<=": "<=",
  between: "between",
  timespan: "timespan",
};

const timespanOptions = [
  {
    label: "Last Week",
    value: "last week",
  },
  {
    label: "Last Month",
    value: "last month",
  },
  {
    label: "Last Quarter",
    value: "last quarter",
  },
  {
    label: "Last 6 Months",
    value: "last 6 months",
  },
  {
    label: "Last Year",
    value: "last year",
  },
  {
    label: "Yesterday",
    value: "yesterday",
  },
  {
    label: "Today",
    value: "today",
  },
  {
    label: "Tomorrow",
    value: "tomorrow",
  },
  {
    label: "This Week",
    value: "this week",
  },
  {
    label: "This Month",
    value: "this month",
  },
  {
    label: "This Quarter",
    value: "this quarter",
  },
  {
    label: "This Year",
    value: "this year",
  },
  {
    label: "Next Week",
    value: "next week",
  },
  {
    label: "Next Month",
    value: "next month",
  },
  {
    label: "Next Quarter",
    value: "next quarter",
  },
  {
    label: "Next 6 Months",
    value: "next 6 months",
  },
  {
    label: "Next Year",
    value: "next year",
  },
];
</script>
