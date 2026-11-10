<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import GlassPanel from "../components/ui/GlassPanel.vue";
import AppButton from "../components/ui/AppButton.vue";
import { request } from "../api/http";
import { failure } from "../api/debates";
import type { Debate } from "../api/debate-contracts";
const debates = ref<Debate[]>([]),
  loading = ref(false),
  error = ref(""),
  more = ref(true);
async function load(reset = false) {
  if (loading.value) return;
  loading.value = true;
  error.value = "";
  try {
    const page = await request<Debate[]>(
      `/debates?limit=20&offset=${reset ? 0 : debates.value.length}`,
    );
    debates.value = reset ? page : [...debates.value, ...page];
    more.value = page.length === 20;
  } catch (e) {
    error.value = failure(e);
  } finally {
    loading.value = false;
  }
}
onMounted(() => load(true));
</script>
<template>
  <main class="debate-page">
    <header class="debate-heading">
      <h1>Мои дебаты</h1>
      <RouterLink class="app-button app-button--primary" to="/debates/new"
        >Новые дебаты</RouterLink
      >
    </header>
    <p v-if="error" role="alert" class="error-message">
      {{ error }} <button @click="load(!debates.length)">Повторить</button>
    </p>
    <GlassPanel class="debate-list"
      ><p v-if="!loading && !error && !debates.length" class="empty-state">
        Здесь появятся ваши дебаты. Выберите тему и начните первую тренировку.
      </p>
      <RouterLink
        v-for="debate in debates"
        :key="debate.id"
        :to="`/debates/${debate.id}`"
        class="debate-row"
        ><div>
          <h2>{{ debate.topic_title }}</h2>
          <p>{{ debate.user_position }}</p>
        </div>
        <span>{{
          new Date(debate.created_at).toLocaleDateString("ru-RU")
        }}</span></RouterLink
      >
      <p v-if="loading" class="empty-state" role="status">
        Загружаем дебаты…
      </p></GlassPanel
    ><AppButton
      v-if="more && debates.length"
      variant="secondary"
      :busy="loading"
      @click="load()"
      >Показать ещё</AppButton
    >
  </main>
</template>
