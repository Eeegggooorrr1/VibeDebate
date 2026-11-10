<script setup lang="ts">
import { computed, useId } from "vue";
interface Option {
  value: string | number | null;
  label: string;
}
const props = withDefaults(
  defineProps<{
    label: string;
    options: Option[];
    modelValue: string | number | null | (string | number)[];
    multiple?: boolean;
    error?: string;
    disabled?: boolean;
    hideLabel?: boolean;
  }>(),
  { multiple: false },
);
const emit = defineEmits<{
  "update:modelValue": [value: string | number | null | (string | number)[]];
}>();
const id = useId();
const errorId = computed(() => `${id}-error`);
function selected(value: Option["value"]) {
  return Array.isArray(props.modelValue)
    ? value !== null && props.modelValue.includes(value)
    : props.modelValue === value;
}
function change(value: Option["value"]) {
  if (!props.multiple) {
    emit("update:modelValue", value);
    return;
  }
  if (value === null) return;
  const values = Array.isArray(props.modelValue) ? [...props.modelValue] : [];
  emit(
    "update:modelValue",
    values.includes(value)
      ? values.filter((item) => item !== value)
      : [...values, value],
  );
}
</script>
<template>
  <fieldset
    class="choice-field"
    :disabled="disabled"
    :aria-describedby="error ? errorId : undefined"
    :aria-invalid="!!error || undefined"
  >
    <legend :class="hideLabel ? 'sr-only' : 'field-label'">{{ label }}</legend>
    <div class="choice-options">
      <label
        v-for="option in options"
        :key="String(option.value)"
        class="choice"
        :class="{ 'choice--selected': selected(option.value) }"
        ><input
          :type="multiple ? 'checkbox' : 'radio'"
          :name="id"
          :checked="selected(option.value)"
          @change="change(option.value)"
        /><span>{{ option.label }}</span></label
      >
    </div>
    <p v-if="error" :id="errorId" class="field-error">{{ error }}</p>
  </fieldset>
</template>
<style src="../../styles/components/choice-group.css"></style>
