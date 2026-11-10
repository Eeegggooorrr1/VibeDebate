<script setup lang="ts">
import { ref } from "vue";
import { ArrowUpRight } from "@lucide/vue";
import GlassPanel from "../components/ui/GlassPanel.vue";
import AppButton from "../components/ui/AppButton.vue";
import { useSession } from "../auth/session";
const session = useSession();
const busy = ref(false);
const error = ref("");
async function authenticate(kind: "login" | "register") {
  busy.value = true;
  error.value = "";
  try {
    await session[kind]();
  } catch {
    error.value = "Не удалось открыть страницу входа.";
    busy.value = false;
  }
}
</script>
<template>
  <main class="welcome-page">
    <GlassPanel class="welcome-panel"
      ><h1>Давайте<br />к аргументам.</h1>
      <div class="welcome-actions">
        <AppButton :busy="busy" @click="authenticate('register')"
          >Создать аккаунт<ArrowUpRight
            :size="18"
            aria-hidden="true" /></AppButton
        ><AppButton
          variant="secondary"
          :disabled="busy"
          @click="authenticate('login')"
          >Войти</AppButton
        >
      </div>
      <p v-if="error || session.error.value" class="error-message" role="alert">
        {{ error || session.error.value }}
      </p></GlassPanel
    >
  </main>
</template>
