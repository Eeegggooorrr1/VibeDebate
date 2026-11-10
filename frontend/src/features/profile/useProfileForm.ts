import { computed, reactive, ref, watch } from "vue";
import { updateProfile } from "../../api/profile";
import { ApiError } from "../../api/http";
import type {
  ProfileDraft,
  ProfileErrors,
  ProfileField,
} from "../../models/profile";
import { validateProfile } from "./validation";
import { useProfile } from "./useProfile";

export function useProfileForm() {
  const { profile, categories } = useProfile();
  const draft = reactive<ProfileDraft>({
    displayName: "",
    level: "",
    interests: [],
    goals: [],
    preferredDifficulty: null,
  });
  const errors = ref<ProfileErrors>({});
  const error = ref("");
  const saving = ref(false);
  const saved = ref(false);
  const submitted = ref(false);
  watch(
    profile,
    (value) => {
      if (value)
        Object.assign(draft, {
          displayName: value.displayName,
          level: value.level ?? "",
          interests: [...value.interests],
          goals: [...value.goals],
          preferredDifficulty: value.preferredDifficulty,
        });
    },
    { immediate: true },
  );
  watch(draft, () => {
    saved.value = false;
    if (submitted.value)
      errors.value = validateProfile(draft, categories.value);
  });
  const categoryOptions = computed(() =>
    categories.value.map((category) => ({
      value: category.id,
      label: category.name,
    })),
  );
  const customGoals = computed(() => draft.goals);
  async function save(): Promise<boolean> {
    if (saving.value) return false;
    submitted.value = true;
    saved.value = false;
    error.value = "";
    errors.value = validateProfile(draft, categories.value);
    if (Object.keys(errors.value).length) return false;
    saving.value = true;
    try {
      profile.value = await updateProfile(draft);
      saved.value = true;
      return true;
    } catch (cause) {
      if (cause instanceof ApiError && cause.details) {
        const mapping: Record<string, ProfileField> = {
          display_name: "displayName",
          level: "level",
          interests: "interests",
          goals: "goals",
          preferred_difficulty: "preferredDifficulty",
        };
        for (const item of cause.details) {
          const key = mapping[String(item.loc[1])];
          if (key) errors.value[key] = "Проверьте значение поля.";
        }
      }
      error.value =
        cause instanceof Error ? cause.message : "Не удалось сохранить анкету.";
      return false;
    } finally {
      saving.value = false;
    }
  }
  return {
    draft,
    errors,
    error,
    saving,
    saved,
    categoryOptions,
    customGoals,
    save,
  };
}
