<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { Check, ArrowUpRight } from "@lucide/vue";
import AppButton from "../../components/ui/AppButton.vue";
import ChoiceGroup from "../../components/ui/ChoiceGroup.vue";
import LiquidDisclosure from "../../components/ui/LiquidDisclosure.vue";
import { useProfileForm } from "./useProfileForm";
import { difficulties, goalOptions, levels } from "./options";
import type { Difficulty, ExperienceLevel } from "../../models/profile";

withDefaults(defineProps<{ editing?: boolean }>(), { editing: false });
const emit = defineEmits<{ saved: [] }>();
const form = ref<HTMLFormElement | null>(null);
const { draft, errors, error, saving, saved, categoryOptions, save } =
  useProfileForm();
const goals = computed(() =>
  [...new Set([...goalOptions, ...draft.goals])].map((goal) => ({
    value: goal,
    label: goal,
  })),
);
async function submit() {
  if (await save()) emit("saved");
  else {
    await nextTick();
    form.value
      ?.querySelector<HTMLElement>(
        '[aria-invalid="true"] input, input[aria-invalid="true"]',
      )
      ?.focus();
  }
}
</script>
<template>
  <form
    ref="form"
    class="profile-form"
    novalidate
    :aria-busy="saving"
    @submit.prevent="submit"
  >
    <div class="form-field">
      <label for="display-name" class="field-label">Имя</label
      ><input
        id="display-name"
        v-model="draft.displayName"
        class="text-input"
        name="display_name"
        autocomplete="nickname"
        maxlength="255"
        required
        :disabled="saving"
        :aria-invalid="!!errors.displayName || undefined"
        :aria-describedby="errors.displayName ? 'name-error' : undefined"
      />
      <p v-if="errors.displayName" id="name-error" class="field-error">
        {{ errors.displayName }}
      </p>
    </div>
    <ChoiceGroup
      label="Ваш уровень"
      :model-value="draft.level"
      :options="levels"
      :disabled="saving"
      :error="errors.level"
      @update:model-value="draft.level = $event as ExperienceLevel"
    />
    <ChoiceGroup
      label="Интересы"
      :model-value="draft.interests"
      :options="categoryOptions"
      multiple
      :disabled="saving"
      :error="errors.interests"
      @update:model-value="draft.interests = $event as string[]"
    />
    <ChoiceGroup
      label="Цели"
      :model-value="draft.goals"
      :options="goals"
      multiple
      :disabled="saving"
      :error="errors.goals"
      @update:model-value="draft.goals = $event as string[]"
    />
    <LiquidDisclosure
      title="Сложность"
      :summary="
        difficulties.find((item) => item.value === draft.preferredDifficulty)
          ?.label
      "
      ><ChoiceGroup
        label="Предпочтительная сложность"
        hide-label
        :model-value="draft.preferredDifficulty"
        :options="difficulties"
        :disabled="saving"
        :error="errors.preferredDifficulty"
        @update:model-value="draft.preferredDifficulty = $event as Difficulty"
    /></LiquidDisclosure>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <div class="form-actions">
      <AppButton type="submit" :busy="saving"
        >{{ editing ? "Сохранить" : "Продолжить"
        }}<ArrowUpRight
          v-if="!saving"
          :size="17"
          aria-hidden="true" /></AppButton
      ><span v-if="saved" class="saved-status" role="status"
        ><Check :size="16" aria-hidden="true" />Сохранено</span
      >
    </div>
  </form>
</template>
<style src="../../styles/features/profile-form.css"></style>
