<script setup lang="ts">
import { RouterView, useRouter } from "vue-router";

import { watch } from "vue";

import { useSession } from "./auth/session";

import { useProfile } from "./features/profile/useProfile";

const router = useRouter();

const { authenticated } = useSession();

watch(authenticated, (value) => {
  if (!value) {
    useProfile().profile.value = null;

    void router.replace("/");
  }
});
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink :to="authenticated ? '/debates' : '/'" class="wordmark"
        >VibeDebate</RouterLink
      >

      <nav
        v-if="authenticated"
        class="main-nav"
        aria-label="Основная навигация"
      >
        <RouterLink to="/debates">Дебаты</RouterLink
        ><RouterLink to="/profile">Профиль</RouterLink>
      </nav>
    </header>

    <RouterView v-slot="{ Component }"
      ><Transition name="page" mode="out-in"
        ><component :is="Component" /></Transition
    ></RouterView>
  </div>
</template>
