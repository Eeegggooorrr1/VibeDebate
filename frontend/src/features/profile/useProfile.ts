import { ref } from "vue";
import { getCategories, getProfile } from "../../api/profile";
import type { Category, Profile } from "../../models/profile";

const profile = ref<Profile | null>(null);
const categories = ref<Category[]>([]);
const loading = ref(false);
const error = ref("");
let pending: Promise<void> | undefined;

async function load() {
  pending ??= (async () => {
    loading.value = true;
    error.value = "";
    try {
      const [user, catalog] = await Promise.all([
        getProfile(),
        getCategories(),
      ]);
      profile.value = user;
      categories.value = catalog;
    } catch (cause) {
      error.value =
        cause instanceof Error
          ? cause.message
          : "Не удалось загрузить профиль.";
    } finally {
      loading.value = false;
      pending = undefined;
    }
  })();
  return pending;
}
export function useProfile() {
  return { profile, categories, loading, error, load };
}
