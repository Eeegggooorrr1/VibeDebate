<script setup lang="ts">
import { ref, useId, onBeforeUnmount, watch } from "vue";
import { ChevronDown } from "@lucide/vue";
import { useLiquidDisclosure } from "../../composables/useLiquidDisclosure";
const props = defineProps<{
  title: string;
  summary?: string;
  open?: boolean;
  modelValue?: boolean;
}>();
const emit = defineEmits<{ "update:modelValue": [value: boolean] }>();
const shell = ref<HTMLElement | null>(null);
const content = ref<HTMLElement | null>(null);
const header = ref<HTMLElement | null>(null);
const id = useId();
const { expanded, toggle, dispose } = useLiquidDisclosure(
  shell,
  content,
  header,
  props.modelValue ?? props.open ?? false,
);
watch(expanded, (value) => emit("update:modelValue", value));
watch(
  () => props.modelValue,
  (value) => {
    if (value !== undefined && value !== expanded.value) void toggle();
  },
);
onBeforeUnmount(dispose);
</script>
<template>
  <section
    ref="shell"
    class="liquid-disclosure"
    :class="{ 'liquid-disclosure--open': expanded }"
  >
    <button
      ref="header"
      type="button"
      class="disclosure-trigger"
      :aria-expanded="expanded"
      :aria-controls="id"
      @click="toggle"
    >
      <span>{{ title }}</span
      ><span v-if="summary" class="disclosure-summary">{{ summary }}</span
      ><ChevronDown :size="17" aria-hidden="true" />
    </button>
    <div
      :id="id"
      ref="content"
      class="disclosure-content"
      :inert="!expanded"
      :aria-hidden="!expanded"
    >
      <slot />
    </div>
  </section>
</template>
<style src="../../styles/components/disclosure.css"></style>
