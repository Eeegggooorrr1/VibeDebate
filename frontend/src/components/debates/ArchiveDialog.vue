<script setup lang="ts">
import { ref, watch } from "vue";
import GlassDialog from "../ui/GlassDialog.vue";
import AppButton from "../ui/AppButton.vue";
import { request } from "../../api/http";
import { failure } from "../../api/debates";
const props = defineProps<{
  target?: { id: string; kind: "chats" | "debates"; title: string };
}>();
const emit = defineEmits<{ close: []; archived: [] }>();
const busy = ref(false),
  error = ref("");
watch(
  () => props.target,
  () => {
    error.value = "";
  },
);
async function remove() {
  if (!props.target || busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await request(`/${props.target.kind}/${props.target.id}`, {
      method: "DELETE",
    });
    emit("archived");
    emit("close");
  } catch (e) {
    error.value = failure(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <GlassDialog
    :model-value="!!target"
    :title="target?.kind === 'debates' ? 'Удалить дебаты?' : 'Удалить чат?'"
    :busy="busy"
    @update:model-value="!$event && emit('close')"
  >
    <p>{{ target?.title }}</p>
    <p class="muted">
      {{
        target?.kind === "debates"
          ? "Дебаты исчезнут из списка вместе со всеми подтемами."
          : "Чат исчезнет из списка подтем."
      }}
    </p>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <div class="suggest-actions">
      <AppButton variant="secondary" :disabled="busy" @click="emit('close')"
        >Отмена</AppButton
      ><AppButton :busy="busy" @click="remove">Удалить</AppButton>
    </div>
  </GlassDialog>
</template>
