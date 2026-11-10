<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
import { X } from "@lucide/vue";
const props = defineProps<{
  modelValue: boolean;
  title: string;
  busy?: boolean;
  fullscreen?: boolean;
}>();
const emit = defineEmits<{ "update:modelValue": [value: boolean] }>();
const dialog = ref<HTMLDialogElement>(),
  id = useId();
let animation: Animation | undefined;
function dismiss() {
  if (!props.busy) emit("update:modelValue", false);
}
async function sync() {
  const el = dialog.value;
  if (!el) return;
  animation?.cancel();
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (props.modelValue) {
    if (!el.open) {
      el.showModal();
      el.scrollTop = 0;
    }
    if (!reduced)
      animation = el.animate(
        [
          { opacity: 0, transform: "translateY(14px) scale(.98)" },
          { opacity: 1, transform: "none" },
        ],
        { duration: 300, easing: "cubic-bezier(.2,1.15,.35,1)" },
      );
  } else if (el.open) {
    if (!reduced) {
      animation = el.animate(
        [
          { opacity: 1, transform: "none" },
          { opacity: 0, transform: "translateY(6px) scale(.99)" },
        ],
        { duration: 140, easing: "ease-out" },
      );
      try {
        await animation.finished;
      } catch {
        return;
      }
    }
    if (!props.modelValue) el.close();
  }
}
watch(() => props.modelValue, sync);
onMounted(sync);
onBeforeUnmount(() => {
  animation?.cancel();
  dialog.value?.close();
});
</script>
<template>
  <Teleport to="body"
    ><dialog
      ref="dialog"
      class="glass-dialog"
      :class="{ 'glass-dialog--fullscreen': fullscreen }"
      :aria-labelledby="id"
      :aria-busy="busy"
      @cancel.prevent="dismiss"
      @click="$event.target === $event.currentTarget && dismiss()"
    >
      <div class="glass-dialog-surface glass-panel">
        <header>
          <h2 :id="id">{{ title }}</h2>
          <button
            class="icon-button"
            aria-label="Закрыть окно"
            :disabled="busy"
            @click="dismiss"
          >
            <X :size="20" />
          </button>
        </header>
        <slot />
      </div></dialog
  ></Teleport>
</template>
