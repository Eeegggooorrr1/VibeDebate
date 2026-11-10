<script setup lang="ts">
withDefaults(defineProps<{ as?: string; inset?: boolean }>(), {
  as: "section",
  inset: false,
});
</script>
<template>
  <component
    :is="as"
    class="glass-panel"
    :class="{ 'glass-panel--inset': inset }"
    ><slot
  /></component>
</template>
<style src="../../styles/components/glass-panel.css"></style>
