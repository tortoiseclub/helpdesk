<template>
  <div class="comm-area">
    <div
      class="flex justify-between gap-3 border-t px-6 md:px-10 py-4 md:py-2.5"
    >
      <div class="flex gap-1.5 items-center">
        <Button
          ref="sendEmailRef"
          variant="ghost"
          label="Reply"
          :class="[showEmailBox ? '!bg-gray-300 hover:!bg-gray-200' : '']"
          @click="toggleEmailBox()"
        >
          <template #prefix>
            <EmailIcon class="h-4" />
          </template>
        </Button>
        <Button
          variant="ghost"
          label="Comment"
          :class="[showCommentBox ? '!bg-gray-300 hover:!bg-gray-200' : '']"
          @click="toggleCommentBox()"
        >
          <template #prefix>
            <CommentIcon class="h-4" />
          </template>
        </Button>
        <TypingIndicator :ticketId="ticketId" />
      </div>
    </div>
    <div
      ref="emailBoxRef"
      v-show="showEmailBox"
      class="flex gap-1.5 flex-1"
      @keydown.ctrl.enter.capture.stop="submitEmail"
      @keydown.meta.enter.capture.stop="submitEmail"
    >
      <EmailEditor
        ref="emailEditorRef"
        :label="
          isMobileView ? 'Send' : isMac ? 'Send (⌘ + ⏎)' : 'Send (Ctrl + ⏎)'
        "
        v-model:content="content"
        placeholder="Hi John, we are looking into this issue."
        :ticketId="ticketId"
        :communicationId="currentCommunicationId"
        :to-emails="toEmails"
        :cc-emails="ccEmails"
        :bcc-emails="bccEmails"
        @submit="handleEmailSent"
        @email-sent="handleEmailSent"
        @discard="
          () => {
            showEmailBox = false;
            isEmailBoxMinimized.value = false;
            currentCommunicationId = null;
          }
        "
      />
    </div>
    <DraftIndicator
      v-if="isEmailBoxMinimized && hasDraft"
      :ticketId="ticketId"
      :communicationId="currentCommunicationId"
      @expand="handleExpandDraft"
      @discard="handleDiscardDraft"
    />
    <div
      ref="commentBoxRef"
      v-show="showCommentBox"
      @keydown.ctrl.enter.capture.stop="submitComment"
      @keydown.meta.enter.capture.stop="submitComment"
    >
      <CommentTextEditor
        ref="commentTextEditorRef"
        :label="
          isMobileView
            ? 'Comment'
            : isMac
            ? 'Comment (⌘ + ⏎)'
            : 'Comment (Ctrl + ⏎)'
        "
        :ticketId="ticketId"
        :editable="showCommentBox"
        :doctype="doctype"
        placeholder="@John could you please look into this?"
        @submit="
          () => {
            showCommentBox = false;
            emit('update');
          }
        "
        @discard="
          () => {
            showCommentBox = false;
          }
        "
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { CommentTextEditor, EmailEditor, TypingIndicator, DraftIndicator } from "@/components";
import { CommentIcon, EmailIcon } from "@/components/icons/";
import { useDevice } from "@/composables";
import { useEmailDraft } from "@/composables/useEmailDraft";
import { useScreenSize } from "@/composables/screen";
import { useShortcut } from "@/composables/shortcuts";
import { showCommentBox, showEmailBox, isEmailBoxMinimized, minimizeEmailBox, expandEmailBox } from "@/pages/ticket/modalStates";
import { computed, nextTick, ref, watch, type Ref } from "vue";
import { onClickOutside } from "@vueuse/core";

const emit = defineEmits(["update"]);
const content = defineModel("content");

const props = defineProps({
  doctype: {
    type: String,
    default: "HD Ticket",
  },
  ticketId: {
    type: String,
    default: null,
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

const { isMac } = useDevice();
const { isMobileView } = useScreenSize();
let doc = defineModel();
// let doc = inject(TicketSymbol)?.value.doc
const emailEditorRef = ref(null);
const commentTextEditorRef = ref(null);
const emailBoxRef = ref(null);
const commentBoxRef = ref(null);

// Track the current communication being replied to
const currentCommunicationId = ref<string | null>(null);

const draftComposable = useEmailDraft(props.ticketId, currentCommunicationId.value);

// Update the composable's communicationId when our ref changes
watch(currentCommunicationId, (newId) => {
  draftComposable.updateCommunicationId(newId);
});

const hasDraft = computed(() => {
  const d = draftComposable.draft.value;
  if (!d) return false;

  // Only consider body content and attachments as a "real" draft.
  // Recipients alone (from initial props) are not a meaningful draft.
  const hasBody = !!(d.content && d.content.trim());
  const hasAttachments = !!(Array.isArray(d.attachments) && d.attachments.length);

  return hasBody || hasAttachments;
});

function toggleEmailBox() {
  if (showCommentBox.value) {
    showCommentBox.value = false;
  }
  if (isEmailBoxMinimized.value) {
    expandEmailBox();
  } else {
  showEmailBox.value = !showEmailBox.value;
  }
}

function toggleCommentBox() {
  if (showEmailBox.value) {
    showEmailBox.value = false;
  }
  showCommentBox.value = !showCommentBox.value;
}

function submitEmail() {
  // Trigger the editor's submit logic; success handling is centralized
  // in handleEmailSent, which is called via the editor's events.
  emailEditorRef.value.submitMail();
}

function submitComment() {
  if (commentTextEditorRef.value.submitComment()) {
    emit("update");
  }
}

function handleEmailSent() {
  showEmailBox.value = false;
  isEmailBoxMinimized.value = false;
  currentCommunicationId.value = null;
  emit("update");
}

function splitIfString(str: string | string[]) {
  if (typeof str === "string") {
    return str.split(",");
  }
  return str;
}

function replyToEmail(data: { communicationId?: string; content: string; to: string | string[]; cc?: string | string[]; bcc?: string | string[] }) {
  // Set the communication ID for this reply
  const newCommunicationId = data.communicationId || null;

  // Update the current communication ID first
  currentCommunicationId.value = newCommunicationId;

  expandEmailBox();
  showEmailBox.value = true;

  // Always call addToReply - it will handle checking for existing drafts and setting up quoted content
  nextTick(() => {
  emailEditorRef.value.addToReply(
    data.content,
    splitIfString(data.to),
      splitIfString(data.cc || []),
      splitIfString(data.bcc || []),
      newCommunicationId
  );
  });
}

function handleExpandDraft() {
  expandEmailBox();
  showEmailBox.value = true;
  nextTick(() => {
    emailEditorRef.value?.editor?.commands?.focus();
  });
}

function handleDiscardDraft() {
  isEmailBoxMinimized.value = false;
  currentCommunicationId.value = null;
}

watch(
  () => showEmailBox.value,
  (value) => {
    if (value) {
      emailEditorRef.value?.editor?.commands?.focus();
    }
  }
);

watch(
  () => showCommentBox.value,
  (value) => {
    if (value) {
      commentTextEditorRef.value?.editor?.commands?.focus();
    }
  }
);

useShortcut("r", () => {
  toggleEmailBox();
});
useShortcut("c", () => {
  toggleCommentBox();
});

defineExpose({
  replyToEmail,
  toggleEmailBox,
  toggleCommentBox,
  editor: emailEditorRef,
});

onClickOutside(
  emailBoxRef,
  () => {
    if (showEmailBox.value) {
      // Check if there's draft content before minimizing
      if (hasDraft.value) {
        minimizeEmailBox();
      } else {
      showEmailBox.value = false;
      }
    }
  },
  {
    ignore: [".tippy-box", ".tippy-content"],
  }
);

onClickOutside(
  commentBoxRef,
  () => {
    if (showCommentBox.value) {
      showCommentBox.value = false;
    }
  },
  {
    ignore: [".tippy-box", ".tippy-content"],
  }
);
</script>

<style>
@media screen and (max-width: 640px) {
  .comm-area {
    width: 100vw;
  }
}
</style>
