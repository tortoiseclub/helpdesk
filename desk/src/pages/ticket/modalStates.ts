import { ref } from "vue";

export const showAssignmentModal = ref(false);
export const showEmailBox = ref(false);
export const showCommentBox = ref(false);
export const isEmailBoxMinimized = ref(false);

export function toggleEmailBox() {
  if (showCommentBox.value) {
    showCommentBox.value = false;
  }
  if (isEmailBoxMinimized.value) {
    isEmailBoxMinimized.value = false;
  }
  showEmailBox.value = !showEmailBox.value;
}

export function minimizeEmailBox() {
  isEmailBoxMinimized.value = true;
  showEmailBox.value = false;
}

export function expandEmailBox() {
  isEmailBoxMinimized.value = false;
  showEmailBox.value = true;
}

export function toggleCommentBox() {
  if (showEmailBox.value) {
    showEmailBox.value = false;
  }
  if (isEmailBoxMinimized.value) {
    isEmailBoxMinimized.value = false;
  }
  showCommentBox.value = !showCommentBox.value;
}
