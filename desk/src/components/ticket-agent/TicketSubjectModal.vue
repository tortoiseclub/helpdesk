<template>
  <Dialog v-model="showSubjectDialog" :options="{ title: 'Rename Subject' }">
    <template #body-content>
      <div class="flex flex-col flex-1 gap-3">
        <!-- Extracted Emails Section -->
        <div v-if="extractedEmails.length > 0" class="mb-2">
          <div class="text-xs text-gray-500 mb-1.5">Emails found in subject:</div>
          <div class="flex flex-wrap gap-2">
            <Button
              v-for="email in extractedEmails"
              :key="email"
              :label="email"
              theme="gray"
              variant="subtle"
              size="sm"
              class="rounded-full"
              title="Click to copy"
              @click="copyEmail(email)"
            >
              <template #suffix>
                <FeatherIcon name="copy" class="h-3 w-3 ml-1" />
              </template>
            </Button>
          </div>
        </div>
        
        <FormControl
          v-model="renameSubject"
          type="textarea"
          size="sm"
          variant="subtle"
          :disabled="false"
        />
        <Button
          variant="solid"
          :loading="isLoading"
          label="Rename"
          @click="handleRename"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { TicketSymbol } from "@/types";
import { toast } from "frappe-ui";
import { computed, inject, ref } from "vue";

const ticket = inject(TicketSymbol);
const showSubjectDialog = defineModel();
const renameSubject = ref(ticket.value?.doc?.subject || "");
const isLoading = ref(false);

// Extract email addresses from subject
const extractedEmails = computed(() => {
  const subject = ticket.value?.doc?.subject || "";
  // Email regex pattern
  const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
  const matches = subject.match(emailRegex);
  return matches ? [...new Set(matches)] : []; // Remove duplicates
});

async function copyEmail(email: string) {
  try {
    await navigator.clipboard.writeText(email);
    toast.info(`Copied "${email}" to clipboard`);
  } catch (err) {
    // Fallback for older browsers
    const textArea = document.createElement("textarea");
    textArea.value = email;
    document.body.appendChild(textArea);
    textArea.select();
    document.execCommand("copy");
    document.body.removeChild(textArea);
    toast.info(`Copied "${email}" to clipboard`);
  }
}

function handleRename() {
  isLoading.value = true;
  ticket.value.setValue.submit(
    {
      subject: renameSubject.value,
    },
    {
      onSuccess() {
        isLoading.value = false;
        showSubjectDialog.value = false;
      },
    }
  );
}
</script>

<style scoped></style>
