<template>
  <Dialog
    v-model="open"
    :options="{
      title: __('Compose New Email'),
      size: '3xl',
    }"
    @close="resetState"
  >
    <template #body-content>
      <div class="flex flex-col gap-4">
        <!-- To -->
        <div class="flex flex-col gap-1">
          <div class="flex items-center gap-2">
            <span class="w-10 shrink-0 text-xs text-ink-gray-5">
              {{ __("To") }}
              <span class="text-red-500">*</span>
            </span>
            <MultiSelectInput
              v-model="toEmails"
              class="flex-1"
              :validate="validateEmail"
              :error-message="(v: string) => `${v} ${__('is an invalid email address')}`"
              field-id="compose-to"
            />
            <Button
              :label="__('CC')"
              :class="[showCC ? 'bg-surface-gray-3' : '']"
              @click="toggleCC"
            />
            <Button
              :label="__('BCC')"
              :class="[showBCC ? 'bg-surface-gray-3' : '']"
              @click="toggleBCC"
            />
          </div>
          <ErrorMessage
            v-if="errors.to"
            class="pl-12"
            :message="errors.to"
          />
        </div>

        <!-- CC -->
        <div v-if="showCC || alwaysCcEmails.length" class="flex items-center gap-2">
          <span class="w-10 shrink-0 text-xs text-ink-gray-5">
            {{ __("CC") }}
          </span>
          <MultiSelectInput
            ref="ccInputRef"
            v-model="ccEmails"
            class="flex-1"
            :validate="validateEmail"
            :error-message="(v: string) => `${v} ${__('is an invalid email address')}`"
            :locked-values="alwaysCcEmails"
            field-id="compose-cc"
          />
        </div>

        <!-- BCC -->
        <div v-if="showBCC" class="flex items-center gap-2">
          <span class="w-10 shrink-0 text-xs text-ink-gray-5">
            {{ __("BCC") }}
          </span>
          <MultiSelectInput
            ref="bccInputRef"
            v-model="bccEmails"
            class="flex-1"
            :validate="validateEmail"
            :error-message="(v: string) => `${v} ${__('is an invalid email address')}`"
            field-id="compose-bcc"
          />
        </div>

        <!-- Subject -->
        <div class="flex flex-col gap-1">
          <div class="flex items-center gap-2">
            <span class="w-10 shrink-0 text-xs text-ink-gray-5">
              {{ __("Subject") }}
              <span class="text-red-500">*</span>
            </span>
            <FormControl
              v-model="subject"
              type="text"
              class="flex-1"
              :placeholder="__('Enter subject')"
              @blur="validateSubject"
            />
          </div>
          <ErrorMessage
            v-if="errors.subject"
            class="pl-12"
            :message="errors.subject"
          />
        </div>

        <!-- Body -->
        <div class="flex flex-col gap-1">
          <TextEditor
            ref="editorRef"
            :editor-class="[
              'prose-sm max-w-full min-h-[10rem] max-h-[35vh] overflow-y-auto py-3 px-4',
            ]"
            :content="body"
            :placeholder="__('Write your message here...')"
            :editable="true"
            :starterkit-options="{ heading: { levels: [2, 3, 4, 5, 6] } }"
            :extensions="[PreserveVideoControls]"
            :upload-function="(file: File) => uploadFunction(file, 'HD Ticket', '_compose')"
            @change="(val: string) => (body = val)"
          >
            <template #bottom>
              <!-- Attachment chips -->
              <div v-if="attachments.length" class="flex flex-wrap gap-2 px-4 pb-2">
                <AttachmentItem
                  v-for="a in attachments"
                  :key="a.file_url"
                  :label="a.file_name"
                  :url="!['MOV', 'MP4'].includes(a.file_type) ? a.file_url : null"
                >
                  <template #suffix>
                    <FeatherIcon
                      class="h-3.5"
                      name="x"
                      @click.self.stop="removeAttachment(a)"
                    />
                  </template>
                </AttachmentItem>
              </div>

              <!-- Toolbar -->
              <div class="flex items-center justify-between border-t px-4 py-2">
                <div class="flex items-center gap-1">
                  <FileUploader
                    :upload-args="{
                      doctype: 'HD Ticket',
                      docname: '_compose',
                      private: true,
                    }"
                    @success="(f) => attachments.push(f)"
                  >
                    <template #default="{ openFileSelector, uploading }">
                      {{ void (isUploading = uploading) }}
                      <Button variant="ghost" :loading="uploading" @click="openFileSelector()">
                        <template #icon>
                          <AttachmentIcon class="h-4" style="color: #000000; stroke-width: 1.5 !important" />
                        </template>
                      </Button>
                    </template>
                  </FileUploader>
                  <TextEditorFixedMenu class="ml-1" :buttons="textEditorMenuButtons" />
                </div>
              </div>
            </template>
          </TextEditor>
          <ErrorMessage
            v-if="errors.body"
            :message="errors.body"
          />
        </div>

        <!-- Actions -->
        <div class="flex items-center justify-end gap-2 pt-1">
          <Button :label="__('Discard')" @click="open = false" />
          <Button
            variant="solid"
            :label="sendResource.loading ? __('Sending...') : __('Send')"
            :loading="sendResource.loading"
            :disabled="isDisabled"
            @click="handleSend"
          />
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { AttachmentItem, MultiSelectInput } from "@/components";
import { AttachmentIcon } from "@/components/icons";
import { PreserveVideoControls } from "@/tiptap-extensions";
import { __ } from "@/translation";
import {
  isContentEmpty,
  removeAttachmentFromServer,
  textEditorMenuButtons,
  uploadFunction,
  validateEmail,
} from "@/utils";
import {
  Dialog,
  ErrorMessage,
  FeatherIcon,
  FileUploader,
  FormControl,
  TextEditor,
  TextEditorFixedMenu,
  createResource,
  toast,
} from "frappe-ui";
import { computed, nextTick, ref, watch } from "vue";
import { useRouter } from "vue-router";

interface Props {
  modelValue: boolean;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (event: "update:modelValue", value: boolean): void;
  (event: "close"): void;
}>();

const router = useRouter();

const open = computed({
  get: () => props.modelValue,
  set: (val) => {
    emit("update:modelValue", val);
    if (!val) emit("close");
  },
});

// ── Form state ────────────────────────────────────────────────────────────────
const toEmails = ref<string[]>([]);
const ccEmails = ref<string[]>([]);
const bccEmails = ref<string[]>([]);
const subject = ref("");
const body = ref<string | null>(null);
const attachments = ref<any[]>([]);
const isUploading = ref(false);
const showCC = ref(false);
const showBCC = ref(false);

const ccInputRef = ref(null);
const bccInputRef = ref(null);
const editorRef = ref(null);

const errors = ref({
  to: "",
  subject: "",
  body: "",
});

// ── Always-CC from HD Settings ────────────────────────────────────────────────
const alwaysCcResource = createResource({
  url: "frappe.client.get_single_value",
  params: { doctype: "HD Settings", field: "always_cc" },
  auto: true,
});

const alwaysCcEmails = computed<string[]>(() => {
  const value: string = alwaysCcResource.data || "";
  if (!value) return [];
  return value
    .split(",")
    .map((e) => e.trim())
    .filter(Boolean);
});

watch(alwaysCcEmails, (emails) => {
  if (!emails.length) return;
  const existing = new Set(ccEmails.value.map((e) => e.toLowerCase()));
  emails.forEach((email) => {
    if (!existing.has(email.toLowerCase())) {
      ccEmails.value.push(email);
    }
  });
  showCC.value = true;
});

// ── Computed helpers ──────────────────────────────────────────────────────────
const isDisabled = computed(
  () =>
    isContentEmpty(body.value) ||
    sendResource.loading ||
    isUploading.value
);

// ── Validation ────────────────────────────────────────────────────────────────
function validateSubject() {
  errors.value.subject =
    !subject.value || !subject.value.trim()
      ? __("Subject is required")
      : "";
  return errors.value.subject;
}

function validateForm(): boolean {
  let hasError = false;

  if (!toEmails.value.length) {
    errors.value.to = __("At least one recipient is required");
    hasError = true;
  } else {
    errors.value.to = "";
  }

  if (validateSubject()) hasError = true;

  if (isContentEmpty(body.value)) {
    errors.value.body = __("Message body is required");
    hasError = true;
  } else {
    errors.value.body = "";
  }

  return !hasError;
}

// ── Toggle CC / BCC ───────────────────────────────────────────────────────────
function toggleCC() {
  showCC.value = !showCC.value;
  if (showCC.value) {
    nextTick(() => ccInputRef.value?.setFocus?.());
  }
}

function toggleBCC() {
  showBCC.value = !showBCC.value;
  if (showBCC.value) {
    nextTick(() => bccInputRef.value?.setFocus?.());
  }
}

// ── Attachments ───────────────────────────────────────────────────────────────
async function removeAttachment(attachment: any) {
  attachments.value = attachments.value.filter(
    (a) => a.name !== attachment.name
  );
  await removeAttachmentFromServer(attachment.name);
}

// ── Send ──────────────────────────────────────────────────────────────────────
const sendResource = createResource({
  url: "helpdesk.api.email.compose_new_email",
  onSuccess: (data: { ticket_id: string; communication_id: string }) => {
    toast.success(__("Email sent successfully"));
    open.value = false;
    router.push({ name: "TicketAgent", params: { ticketId: data.ticket_id } });
  },
  onError: (err: any) => {
    toast.error(err?.message || __("Failed to send email"));
  },
});

function handleSend() {
  if (!validateForm()) return;

  sendResource.submit({
    to: toEmails.value.join(","),
    subject: subject.value.trim(),
    message: body.value,
    cc: ccEmails.value.join(",") || null,
    bcc: bccEmails.value.join(",") || null,
    attachments: attachments.value.map((a) => a.name),
  });
}

// ── Reset ─────────────────────────────────────────────────────────────────────
function resetState() {
  toEmails.value = [];
  ccEmails.value = [];
  bccEmails.value = [];
  subject.value = "";
  body.value = null;
  attachments.value = [];
  isUploading.value = false;
  showCC.value = false;
  showBCC.value = false;
  errors.value = { to: "", subject: "", body: "" };
}
</script>
