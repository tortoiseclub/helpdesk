<template>
  <TextEditor
    ref="editorRef"
    :editor-class="[
      'prose-sm max-w-full mx-6 md:mx-10 max-h-[50vh] py-3',
      'min-h-[7rem]',
      getFontFamily(newEmail),
      editable && '!max-h-[35vh] overflow-y-auto',
    ]"
    :content="newEmail"
    :starterkit-options="{ heading: { levels: [2, 3, 4, 5, 6] } }"
    :placeholder="placeholder"
    :editable="editable"
    @change="editable ? (newEmail = $event) : null"
    :extensions="[PreserveVideoControls]"
    :uploadFunction="(file:any)=>uploadFunction(file, doctype, ticketId)"
  >
    <template #top>
      <div class="mx-6 md:mx-10 flex items-center gap-2 border-y py-2.5">
        <span class="text-xs text-gray-500">TO:</span>
        <MultiSelectInput
          v-model="toEmailsClone"
          class="flex-1"
          :validate="validateEmail"
          :error-message="(value) => `${value} is an invalid email address`"
          field-id="to"
          @email-dropped="handleEmailDrop"
        />
        <Button
          :label="'CC'"
          :class="[cc ? 'bg-gray-300 hover:bg-gray-200' : '']"
          @click="toggleCC()"
        />
        <Button
          :label="'BCC'"
          :class="[bcc ? 'bg-gray-300 hover:bg-gray-200' : '']"
          @click="toggleBCC()"
        />
      </div>
      <div
        v-if="showCC || cc || alwaysCcEmails.length"
        class="mx-10 flex items-center gap-2 py-2.5"
        :class="cc || showCC || alwaysCcEmails.length ? 'border-b' : ''"
      >
        <span class="text-xs text-gray-500">CC:</span>
        <MultiSelectInput
          ref="ccInput"
          v-model="ccEmailsClone"
          class="flex-1"
          :validate="validateEmail"
          :error-message="(value: string) => `${value} is an invalid email address`"
          :locked-values="alwaysCcEmails"
          field-id="cc"
          @email-dropped="handleEmailDrop"
        />
      </div>
      <div
        v-if="showBCC || bcc"
        class="mx-10 flex items-center gap-2 py-2.5"
        :class="bcc || showBCC ? 'border-b' : ''"
      >
        <span class="text-xs text-gray-500">BCC:</span>
        <MultiSelectInput
          ref="bccInput"
          v-model="bccEmailsClone"
          class="flex-1"
          :validate="validateEmail"
          :error-message="(value) => `${value} is an invalid email address`"
          field-id="bcc"
          @email-dropped="handleEmailDrop"
        />
      </div>
    </template>
    <!-- <template v-slot:editor="{ _editor }">
      <EditorContent
        :class="[editable && 'max-h-[35vh] overflow-y-auto']"
        :editor="_editor"
      />
    </template> -->
    <template #bottom>
      <!-- Attachments -->
      <div class="flex flex-wrap gap-2 px-10">
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
      <!-- TextEditor Fixed Menu -->
      <div
        class="flex justify-between overflow-scroll pl-10 py-2.5 items-center"
      >
        <div class="flex items-center overflow-x-auto w-[60%]">
          <div class="flex gap-1">
            <FileUploader
              :upload-args="{
                doctype: doctype,
                docname: ticketId,
                private: true,
              }"
              @success="
                (f) => {
                  attachments.push(f);
                }
              "
            >
              <template #default="{ openFileSelector, uploading }">
                {{ void (isUploading = uploading) }}
                <Button
                  variant="ghost"
                  @click="openFileSelector()"
                  :loading="uploading"
                >
                  <template #icon>
                    <AttachmentIcon
                      class="h-4"
                      style="color: #000000; stroke-width: 1.5 !important"
                    />
                  </template>
                </Button>
              </template>
            </FileUploader>
            <Button
              variant="ghost"
              @click="showSavedRepliesSelectorModal = true"
            >
              <template #icon>
                <SavedReplyIcon class="h-4" />
              </template>
            </Button>
          </div>
          <TextEditorFixedMenu class="ml-1" :buttons="textEditorMenuButtons" />
        </div>
        <div
          class="flex items-center justify-end space-x-2 sm:mt-0 w-[40%] mr-9"
        >
          <Button label="Discard" @click="handleDiscard" />
          <Button
            variant="solid"
            :disabled="isDisabled"
            :loading="sendMail.loading"
            :label="label"
            @click="
              () => {
                submitMail();
              }
            "
          />
        </div>
      </div>
    </template>
  </TextEditor>
  <SavedRepliesSelectorModal
    v-if="showSavedRepliesSelectorModal"
    v-model="showSavedRepliesSelectorModal"
    :doctype="doctype"
    @apply="applySavedReplies"
    :ticketId="ticketId"
  />
</template>

<script setup lang="ts">
import {
  AttachmentItem,
  SavedRepliesSelectorModal,
  MultiSelectInput,
} from "@/components";
import { AttachmentIcon } from "@/components/icons";
import { useTyping } from "@/composables/realtime";
import { useAuthStore } from "@/stores/auth";
import { PreserveVideoControls } from "@/tiptap-extensions";
import {
  getFontFamily,
  isContentEmpty,
  removeAttachmentFromServer,
  textEditorMenuButtons,
  uploadFunction,
  validateEmail,
} from "@/utils";
// import { EditorContent } from "@tiptap/vue-3";
import { useStorage } from "@vueuse/core";
import {
  FileUploader,
  TextEditor,
  TextEditorFixedMenu,
  createResource,
  toast,
} from "frappe-ui";
import { useOnboarding } from "frappe-ui/frappe";
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import SavedReplyIcon from "./icons/SavedReplyIcon.vue";

const editorRef = ref(null);
const showSavedRepliesSelectorModal = ref(false);

const props = defineProps({
  ticketId: {
    type: String,
    default: null,
  },
  placeholder: {
    type: String,
    default: null,
  },
  label: {
    type: String,
    default: "Send",
  },
  editable: {
    type: Boolean,
    default: true,
  },
  doctype: {
    type: String,
    default: "HD Ticket",
  },
  toEmails: {
    type: Array,
    default: () => [],
  },
  ccEmails: {
    type: Array,
    default: () => [],
  },
  bccEmails: {
    type: Array,
    default: () => [],
  },
});

const label = computed(() => {
  return sendMail.loading ? "Sending..." : props.label;
});

const emit = defineEmits(["submit", "discard"]);

const newEmail = useStorage("emailBoxContent" + props.ticketId, null);
const { updateOnboardingStep } = useOnboarding("helpdesk");
const { isManager } = useAuthStore();

// Initialize typing composable
const { onUserType, cleanup } = useTyping(props.ticketId);

const attachments = ref([]);
const isUploading = ref(false);
const isDisabled = computed(() => {
  return (
    isContentEmpty(newEmail.value) || sendMail.loading || isUploading.value
  );
});

// Watch for changes in email content to trigger typing events
watch(newEmail, (newValue, oldValue) => {
  if (newValue !== oldValue && newValue) {
    onUserType();
  }
});

onBeforeUnmount(() => {
  cleanup();
});

const toEmailsClone = ref([...props.toEmails]);
const ccEmailsClone = ref([...props.ccEmails]);
const bccEmailsClone = ref([...props.bccEmails]);
const showCC = ref(false);
const showBCC = ref(false);
const cc = computed(() => (ccEmailsClone.value?.length ? true : false));
const bcc = computed(() => (bccEmailsClone.value?.length ? true : false));
const ccInput = ref(null);
const bccInput = ref(null);

function applySavedReplies(template) {
  newEmail.value = template;
  showSavedRepliesSelectorModal.value = false;
}

// Fetch always CC emails from HD Settings
const alwaysCcResource = createResource({
  url: "frappe.client.get_single_value",
  params: {
    doctype: "HD Settings",
    field: "always_cc",
  },
  auto: true,
});

const alwaysCcEmails = computed(() => {
  const value = alwaysCcResource.data || "";
  if (!value) return [];
  return value
    .split(",")
    .map((email: string) => email.trim())
    .filter((email: string) => email);
});

// Initialize CC with always CC emails when they load
watch(
  alwaysCcEmails,
  (emails) => {
    if (emails.length > 0) {
      // Add always CC emails if not already present
      const currentCc = new Set(ccEmailsClone.value.map((e) => e.toLowerCase()));
      emails.forEach((email: string) => {
        if (!currentCc.has(email.toLowerCase())) {
          ccEmailsClone.value.push(email);
        }
      });
      // Auto-show CC section when there are always CC emails
      showCC.value = true;
    }
  },
  { immediate: true }
);

const sendMail = createResource({
  url: "run_doc_method",
  makeParams: () => ({
    dt: props.doctype,
    dn: props.ticketId,
    method: "reply_via_agent",
    args: {
      attachments: attachments.value.map((x) => x.name),
      to: toEmailsClone.value.join(","),
      cc: ccEmailsClone.value?.join(","),
      bcc: bccEmailsClone.value?.join(","),
      message: newEmail.value,
    },
  }),
  onSuccess: () => {
    resetState();
    emit("submit");

    if (isManager) {
      updateOnboardingStep("reply_on_ticket");
    }
  },
  debounce: 300,
});

function submitMail() {
  if (isContentEmpty(newEmail.value)) {
    return false;
  }
  if (!toEmailsClone.value.length) {
    toast.warning(
      "Email has no recipients. Please add at least one email address in the 'TO' field."
    );
    return false;
  }

  sendMail.submit();
}

function toggleCC() {
  showCC.value = !showCC.value;

  showCC.value &&
    nextTick(() => {
      ccInput.value.setFocus();
    });
}

function toggleBCC() {
  showBCC.value = !showBCC.value;
  showBCC.value &&
    nextTick(() => {
      bccInput.value.setFocus();
    });
}

// Handle email drag and drop between TO, CC, BCC fields
function handleEmailDrop({ email, sourceField, targetField }: { email: string; sourceField: string; targetField: string }) {
  // Remove from source field (unless it's a locked value)
  const isLockedInCc = alwaysCcEmails.value.some(
    (e: string) => e.toLowerCase() === email.toLowerCase()
  );
  
  if (sourceField === "to") {
    toEmailsClone.value = toEmailsClone.value.filter((e) => e !== email);
  } else if (sourceField === "cc" && !isLockedInCc) {
    ccEmailsClone.value = ccEmailsClone.value.filter((e) => e !== email);
  } else if (sourceField === "bcc") {
    bccEmailsClone.value = bccEmailsClone.value.filter((e) => e !== email);
  }
  
  // Auto-show CC/BCC sections when dropping into them
  if (targetField === "cc") {
    showCC.value = true;
  } else if (targetField === "bcc") {
    showBCC.value = true;
  }
}

async function removeAttachment(attachment) {
  attachments.value = attachments.value.filter((a) => a !== attachment);
  await removeAttachmentFromServer(attachment.name);
}

/**
 * Sanitizes HTML content for use in quoted replies.
 * Converts tables to simple paragraphs to avoid rendering issues in the editor.
 */
function sanitizeQuotedContent(html: string): string {
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, "text/html");

  // Process all tables - convert them to simple paragraphs with their text content
  const tables = doc.querySelectorAll("table");
  tables.forEach((table) => {
    const rows = table.querySelectorAll("tr");
    const fragment = doc.createDocumentFragment();

    rows.forEach((row) => {
      const cells = row.querySelectorAll("td, th");
      const cellContents: string[] = [];

      cells.forEach((cell) => {
        // Get the innerHTML to preserve inline formatting (bold, links, etc.)
        const content = cell.innerHTML.trim();
        if (content) {
          cellContents.push(content);
        }
      });

      if (cellContents.length > 0) {
        const p = doc.createElement("p");
        p.innerHTML = cellContents.join(" ");
        fragment.appendChild(p);
      }
    });

    // Replace the table with the simplified content
    if (fragment.childNodes.length > 0) {
      table.parentNode?.replaceChild(fragment, table);
    } else {
      table.remove();
    }
  });

  return doc.body.innerHTML;
}

function addToReply(
  body: string,
  toEmails: string[],
  ccEmails: string[],
  bccEmails: string[]
) {
  toEmailsClone.value = toEmails;
  // Merge always CC emails with provided CC emails
  const allCc = new Set([
    ...alwaysCcEmails.value.map((e: string) => e.toLowerCase()),
    ...ccEmails.map((e) => e.toLowerCase()),
  ]);
  // Rebuild with original case, prioritizing always CC
  const mergedCc: string[] = [...alwaysCcEmails.value];
  ccEmails.forEach((email) => {
    if (!alwaysCcEmails.value.some((e: string) => e.toLowerCase() === email.toLowerCase())) {
      mergedCc.push(email);
    }
  });
  ccEmailsClone.value = mergedCc;
  bccEmailsClone.value = bccEmails;
  // Show CC if there are any CC emails
  if (mergedCc.length > 0) {
    showCC.value = true;
  }

  // Sanitize the quoted content to handle tables properly
  const sanitizedBody = sanitizeQuotedContent(body);

  editorRef.value.editor
    .chain()
    .clearContent()
    .insertContent(sanitizedBody)
    .focus("all")
    .setBlockquote()
    .insertContentAt(0, { type: "paragraph" })
    .focus("start")
    .run();
}

function resetState() {
  newEmail.value = null;
  attachments.value = [];
}

function handleDiscard() {
  attachments.value = [];
  newEmail.value = null;

  // Keep always CC emails, remove others
  ccEmailsClone.value = [...alwaysCcEmails.value];
  bccEmailsClone.value = [];
  // Show CC section if there are always CC emails
  showCC.value = alwaysCcEmails.value.length > 0;
  showBCC.value = false;

  emit("discard");
}

const editor = computed(() => {
  return editorRef.value.editor;
});

defineExpose({
  addToReply,
  editor,
  submitMail,
});
</script>
