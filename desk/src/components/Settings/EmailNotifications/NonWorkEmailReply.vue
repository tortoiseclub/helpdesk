<template>
  <Notification
    v-model:content="content"
    :defaultContent="defaultContent"
    v-model:enabled="enabled"
    documentationLink="https://docs.frappe.io/helpdesk/email-notifications"
    ref="compRef"
    name="non_work_email_reply"
    :title="props.notification.label"
    :description="props.notification.description"
    :submitting="updateSettings.loading"
    :onBack="props.onBack"
    :onSubmit="onSubmit"
    :onGetDataSuccess="onGetDataSuccess"
  >
    <template #formFields>
      <div class="flex flex-col gap-4">
        <FormControl
          type="textarea"
          size="sm"
          :label="__('Blacklisted Domains')"
          :description="
            __(
              'Comma-separated list of email domains considered as non-work/personal email providers (e.g., gmail.com, yahoo.com)'
            )
          "
          :rows="3"
          v-model="domains"
          :oninput="setUnsavedChanges"
        />
        <FormControl
          type="number"
          size="sm"
          :label="__('Throttle Period (Days)')"
          :description="
            __(
              'Number of days to wait before sending another auto-reply to the same email address. This prevents spam.'
            )
          "
          v-model="throttleDays"
          :oninput="setUnsavedChanges"
        />
      </div>
    </template>
  </Notification>
</template>

<script setup lang="ts">
import { ref } from "vue";
import Notification from "./Notification.vue";
import { createResource, FormControl } from "frappe-ui";
import { __ } from "@/translation";
import type { BaseSettings, Notification as NotificationType } from "./types";

const props = defineProps<{
  onBack: () => void;
  notification: NotificationType;
}>();

const content = ref("");
const defaultContent = ref("");
const enabled = ref(false);
const domains = ref("");
const throttleDays = ref(7);
const compRef = ref<InstanceType<typeof Notification>>();

type NonWorkEmailReplySettings = BaseSettings & {
  domains: string;
  throttle_days: number;
  default_content: string;
};

const updateSettings = createResource({
  url: "helpdesk.api.settings.email_notifications.update_non_work_email_reply",
  method: "PUT",
  auto: false,
  onSuccess(data: NonWorkEmailReplySettings) {
    enabled.value = data.enabled;
    content.value = data.content;
    domains.value = data.domains;
    throttleDays.value = data.throttle_days;
    compRef.value?.resetUnsavedChanges();
  },
});

function onSubmit() {
  return updateSettings.submit({
    enabled: enabled.value,
    content: content.value,
    domains: domains.value,
    throttle_days: throttleDays.value,
  });
}

function onGetDataSuccess(data: NonWorkEmailReplySettings) {
  enabled.value = data.enabled;
  content.value = data.content;
  defaultContent.value = data.default_content;
  domains.value = data.domains;
  throttleDays.value = data.throttle_days;
}

function setUnsavedChanges() {
  compRef.value?.setUnsavedChanges();
}
</script>
