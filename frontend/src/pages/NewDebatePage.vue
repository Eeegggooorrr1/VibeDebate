<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import GlassPanel from "../components/ui/GlassPanel.vue";
import LiquidDisclosure from "../components/ui/LiquidDisclosure.vue";
import AppButton from "../components/ui/AppButton.vue";
import { request } from "../api/http";
import { allPages, post, failure } from "../api/debates";
import type { Debate, Topic, Persona, Category } from "../api/debate-contracts";
const router = useRouter();
const topicsLoading = ref(false);
const step = ref(0),
  stepHeading = ref<HTMLElement>();
const steps = [
  "Категория",
  "Тема",
  "Ваша позиция",
  "Оппонент",
  "Сложность",
  "Всё готово",
];
const canContinue = computed(() =>
  step.value === 1
    ? custom.value
      ? !!customTopic.value.trim()
      : !topicsLoading.value && !!topicId.value
    : step.value === 2
      ? !!position.value.trim()
      : !loading.value,
);
async function go(value: number) {
  step.value = value;
  await nextTick();
  stepHeading.value?.focus();
}

const categories = ref<Category[]>([]),
  topics = ref<Topic[]>([]),
  personas = ref<Persona[]>([]);
const category = ref(""),
  topicId = ref(""),
  custom = ref(false),
  customTopic = ref(""),
  position = ref(""),
  persona = ref(""),
  difficulty = ref(1),
  loading = ref(true),
  busy = ref(false),
  error = ref(""),
  topicError = ref("");
const selected = computed(() =>
  topics.value.find((t) => t.id === topicId.value),
);
const levels = computed(
  () =>
    personas.value.find((p) => p.id === persona.value)
      ?.available_difficulties || [1, 2, 3],
);
watch(levels, (v) => {
  if (!v.includes(difficulty.value)) difficulty.value = v[0] || 1;
});
let topicVersion = 0;
async function loadTopics() {
  const version = ++topicVersion;
  topicError.value = "";
  topicId.value = "";
  topics.value = [];
  topicsLoading.value = true;
  try {
    const data = await allPages<Topic>(
      `/topics${category.value ? `?category_id=${category.value}` : ""}`,
    );
    if (version === topicVersion) topics.value = data;
  } catch (e) {
    if (version === topicVersion) topicError.value = failure(e);
  } finally {
    if (version === topicVersion) topicsLoading.value = false;
  }
}
watch(category, loadTopics);
async function load() {
  loading.value = true;
  error.value = "";
  try {
    [categories.value, personas.value] = await Promise.all([
      request<Category[]>("/topics/categories"),
      request<Persona[]>("/topics/opponents"),
    ]);
    persona.value = personas.value[0]?.id || "";
    await loadTopics();
  } catch (e) {
    error.value = failure(e);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
async function create() {
  if (step.value !== 5 || busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const debate = await post<Debate>("/debates/advanced", {
      ...(custom.value
        ? { custom_topic: customTopic.value.trim() }
        : { topic_id: topicId.value }),
      user_position: position.value.trim(),
      ...(persona.value ? { opponent_persona_id: persona.value } : {}),
      difficulty: difficulty.value,
    });
    await router.push(`/debates/${debate.id}`);
  } catch (e) {
    error.value = failure(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <main class="debate-page create-page">
    <RouterLink to="/debates" class="muted">К моим дебатам</RouterLink>
    <header class="debate-heading">
      <h1>Новые дебаты</h1>
      <span class="muted">Продвинутый режим</span>
    </header>
    <GlassPanel class="create-panel wizard-panel">
      <nav class="wizard-progress" aria-label="Этапы создания">
        <button
          v-for="(name, i) in steps"
          :key="name"
          :disabled="i >= step || busy"
          :aria-current="step === i ? 'step' : undefined"
          :aria-label="name"
          @click="go(i)"
        >
          <span>{{ i + 1 }}</span
          ><span>{{ name }}</span>
        </button>
      </nav>
      <p v-if="loading" role="status" class="empty-state">Загружаем каталог…</p>
      <form
        v-else
        class="debate-form"
        @submit.prevent="step < 5 ? canContinue && go(step + 1) : create()"
      >
        <Transition
          name="step"
          mode="out-in"
          @after-enter="stepHeading?.focus()"
          ><section :key="step" class="wizard-step">
            <h2 ref="stepHeading" tabindex="-1">
              {{
                [
                  "Что вам интересно?",
                  custom ? "О чём будем спорить?" : "Выберите тему",
                  "Какую позицию вы займёте?",
                  "Кто будет вашим оппонентом?",
                  "Насколько сложным будет спор?",
                  "Начнём дебаты?",
                ][step]
              }}
            </h2>
            <fieldset :disabled="busy">
              <legend class="sr-only">{{ steps[step] }}</legend>
              <template v-if="step === 0"
                ><div class="mode-switch">
                  <button
                    type="button"
                    :aria-pressed="!custom"
                    @click="custom = false"
                  >
                    Из каталога</button
                  ><button
                    type="button"
                    :aria-pressed="custom"
                    @click="custom = true"
                  >
                    Своя тема
                  </button>
                </div>
                <div v-if="!custom" class="wizard-choices">
                  <button
                    type="button"
                    class="layer-choice"
                    :aria-pressed="category === ''"
                    @click="category = ''"
                  >
                    Все категории</button
                  ><button
                    v-for="c in categories"
                    :key="c.id"
                    type="button"
                    class="layer-choice"
                    :aria-pressed="category === c.id"
                    @click="category = c.id"
                  >
                    {{ c.name }}
                  </button>
                </div>
                <p v-else class="muted">
                  Сформулируйте собственную тему на следующем шаге.
                </p></template
              >
              <template v-else-if="step === 1"
                ><label v-if="custom"
                  >Тема<textarea
                    v-model="customTopic"
                    class="text-input"
                    rows="4"
                    maxlength="2000"
                    required
                  />
                </label>
                <div
                  v-else
                  class="wizard-choices topic-choices"
                  role="group"
                  aria-label="Темы"
                >
                  <button
                    v-for="t in topics"
                    :key="t.id"
                    type="button"
                    class="layer-choice"
                    :aria-pressed="topicId === t.id"
                    @click="topicId = t.id"
                  >
                    <strong>{{ t.title }}</strong
                    ><span>{{ t.description }}</span>
                  </button>
                  <p
                    v-if="!topics.length && !topicError && !topicsLoading"
                    class="muted"
                  >
                    Тем в этой категории пока нет. Выберите другую категорию или
                    предложите свою тему.
                  </p>
                </div>
                <p v-if="topicError" role="alert" class="error-message">
                  {{ topicError }}
                  <button type="button" @click="loadTopics">Повторить</button>
                </p></template
              >
              <template v-else-if="step === 2"
                ><GlassPanel inset class="wizard-context">{{
                  custom ? customTopic : selected?.title
                }}</GlassPanel>
                <div
                  v-if="!custom && selected?.default_positions.length"
                  class="wizard-choices"
                >
                  <button
                    v-for="p in selected.default_positions"
                    :key="p"
                    type="button"
                    class="layer-choice"
                    :aria-pressed="position === p"
                    @click="position = p"
                  >
                    {{ p }}
                  </button>
                </div>
                <label
                  >Ваша позиция<textarea
                    v-model="position"
                    class="text-input"
                    required
                    maxlength="4000"
                    rows="4"
                  /></label
              ></template>
              <template v-else-if="step === 3"
                ><div class="wizard-choices">
                  <button
                    v-for="p in personas"
                    :key="p.id"
                    type="button"
                    class="layer-choice"
                    :aria-pressed="persona === p.id"
                    @click="persona = p.id"
                  >
                    <strong>{{ p.name }}</strong
                    ><span>{{ p.description }}</span>
                  </button>
                  <p v-if="!personas.length" class="muted">
                    Будет выбран оппонент по умолчанию.
                  </p>
                </div></template
              >
              <template v-else-if="step === 4"
                ><div class="wizard-choices">
                  <button
                    v-for="n in levels"
                    :key="n"
                    type="button"
                    class="layer-choice"
                    :aria-pressed="difficulty === n"
                    @click="difficulty = n"
                  >
                    {{ ["Начальная", "Средняя", "Высокая"][n - 1] }}
                  </button>
                </div></template
              >
              <template v-else
                ><GlassPanel inset class="wizard-context"
                  ><h3>{{ custom ? customTopic : selected?.title }}</h3>
                  <p>{{ position }}</p></GlassPanel
                ><LiquidDisclosure
                  title="Настройки"
                  :summary="personas.find((p) => p.id === persona)?.name"
                  ><dl class="review-settings">
                    <dt>Оппонент</dt>
                    <dd>
                      {{
                        personas.find((p) => p.id === persona)?.name ||
                        "По умолчанию"
                      }}
                    </dd>
                    <dt>Сложность</dt>
                    <dd>
                      {{ ["Начальная", "Средняя", "Высокая"][difficulty - 1] }}
                    </dd>
                  </dl></LiquidDisclosure
                ></template
              >
            </fieldset>
          </section></Transition
        >
        <p v-if="error" class="error-message" role="alert">{{ error }}</p>
        <footer class="wizard-actions">
          <AppButton
            variant="quiet"
            :disabled="step === 0 || busy"
            @click="go(step - 1)"
            >Назад</AppButton
          ><AppButton type="submit" :busy="busy" :disabled="!canContinue">{{
            busy
              ? "Готовим дебаты…"
              : step === 5
                ? "Начать дебаты"
                : "Продолжить"
          }}</AppButton>
        </footer>
      </form>
      <AppButton v-if="error && !personas.length" variant="quiet" @click="load"
        >Обновить каталог</AppButton
      >
    </GlassPanel>
  </main>
</template>
