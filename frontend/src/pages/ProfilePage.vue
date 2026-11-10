<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { ArrowLeft, LogOut, RefreshCw } from "@lucide/vue";
import LiquidDisclosure from "../components/ui/LiquidDisclosure.vue";
import GlassPanel from "../components/ui/GlassPanel.vue";
import AppButton from "../components/ui/AppButton.vue";
import ProfileForm from "../features/profile/ProfileForm.vue";
import { useProfile } from "../features/profile/useProfile";
import { useSession } from "../auth/session";
import { levels, difficulties } from "../features/profile/options";
const props = defineProps<{ onboarding?: boolean }>();
const router = useRouter();
const { profile, categories, loading, error, load } = useProfile();
const session = useSession();
const editing = ref(false);
const logoutError = ref("");
const interests = computed(() =>
  categories.value
    .filter((category) => profile.value?.interests.includes(category.id))
    .map((category) => category.name),
);
const showForm = computed(() => props.onboarding || editing.value);
async function finish() {
  editing.value = false;
  if (props.onboarding) await router.replace("/profile");
}
async function logout() {
  try {
    await session.logout();
  } catch {
    logoutError.value = "Не удалось выйти. Попробуйте ещё раз.";
  }
}
async function retry() {
  await load();
  if (profile.value && !profile.value.onboardingCompleted)
    await router.replace("/onboarding");
}
</script>
<template>
  <main class="profile-page">
    <GlassPanel class="profile-panel">
      <header class="panel-header">
        <div>
          <button
            v-if="editing && !onboarding"
            type="button"
            class="back-button"
            aria-label="Назад к профилю"
            @click="editing = false"
          >
            <ArrowLeft :size="18" />
          </button>
          <h1>
            {{
              onboarding
                ? "Ваша анкета"
                : editing
                  ? "Редактирование"
                  : "Профиль"
            }}
          </h1>
        </div>
        <button class="icon-button" aria-label="Выйти" @click="logout">
          <LogOut :size="19" />
        </button>
      </header>
      <p v-if="logoutError" class="error-message" role="alert">
        {{ logoutError }}
      </p>
      <div v-if="loading" class="loading-state" role="status">Загрузка…</div>
      <div v-else-if="error" class="load-error">
        <p class="error-message" role="alert">{{ error }}</p>
        <AppButton variant="secondary" @click="retry"
          ><RefreshCw :size="16" />Повторить</AppButton
        >
      </div>
      <ProfileForm
        v-else-if="profile && showForm"
        :key="String(editing)"
        :editing="!onboarding"
        @saved="finish"
      />
      <div v-else-if="profile" class="profile-summary">
        <div class="profile-layers">
          <GlassPanel inset class="profile-identity"
            ><span class="profile-avatar" aria-hidden="true">{{
              profile.displayName.slice(0, 1)
            }}</span>
            <div>
              <h2>{{ profile.displayName }}</h2>
              <p class="muted">
                {{
                  levels.find((item) => item.value === profile?.level)?.label
                }}
              </p>
            </div></GlassPanel
          >
          <LiquidDisclosure
            title="Интересы"
            :summary="String(interests.length)"
            :open="true"
            ><div class="profile-tags">
              <span
                v-for="interest in interests"
                :key="interest"
                class="profile-tag"
                >{{ interest }}</span
              >
              <p v-if="!interests.length" class="muted">Не выбраны</p>
            </div></LiquidDisclosure
          >
          <LiquidDisclosure
            title="Цели"
            :summary="String(profile.goals.length)"
            :open="true"
            ><div class="profile-tags">
              <span
                v-for="goal in profile.goals"
                :key="goal"
                class="profile-tag"
                >{{ goal }}</span
              >
            </div></LiquidDisclosure
          >
          <LiquidDisclosure
            title="Сложность"
            :summary="
              difficulties.find(
                (item) => item.value === profile?.preferredDifficulty,
              )?.label
            "
            ><p>
              {{
                difficulties.find(
                  (item) => item.value === profile?.preferredDifficulty,
                )?.label
              }}
            </p></LiquidDisclosure
          >
        </div>
        <AppButton variant="secondary" @click="editing = true"
          >Редактировать</AppButton
        >
      </div>
    </GlassPanel>
  </main>
</template>
