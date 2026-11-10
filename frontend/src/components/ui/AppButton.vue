<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: "primary" | "secondary" | "quiet";
    busy?: boolean;
    disabled?: boolean;
    type?: "button" | "submit";
  }>(),
  { variant: "primary", busy: false, disabled: false, type: "button" },
);
</script>
<template>
  <button
    class="app-button"
    :class="`app-button--${variant}`"
    :type="type"
    :disabled="disabled || busy"
    :aria-busy="busy || undefined"
  >
    <slot /><span v-if="busy" class="button-spinner" aria-hidden="true" />
  </button>
</template>
<style src="../../styles/components/button.css"></style>
