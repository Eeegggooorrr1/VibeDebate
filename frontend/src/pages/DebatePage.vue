<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Plus, WandSparkles, CircleHelp, RotateCw } from "@lucide/vue";
import AnalysisPanel from "../components/debates/AnalysisPanel.vue";
import { useAnalysis } from "../features/debates/useAnalysis";
import { useSuggestions } from "../features/debates/useSuggestions";
import GlassDialog from "../components/ui/GlassDialog.vue";
import LiquidDisclosure from "../components/ui/LiquidDisclosure.vue";
import MessageContent from "../components/ui/MessageContent.vue";
import GlassPanel from "../components/ui/GlassPanel.vue";
import AppButton from "../components/ui/AppButton.vue";
import { request, ApiError } from "../api/http";
import {
  allPages,
  post,
  failure,
  sendTurn,
  mergeMessage,
} from "../api/debates";
import type { Debate, Chat, Message, Persona } from "../api/debate-contracts";
const route = useRoute(),
  router = useRouter();
const debate = ref<Debate>(),
  chat = ref<Chat>(),
  messages = ref<Message[]>([]),
  personas = ref<Persona[]>([]);
const loading = ref(false),
  historyLoading = ref(false),
  sending = ref(false),
  creating = ref(false),
  showCreate = ref(false),
  composerOpen = ref(false),
  createError = ref(""),
  argumentInput = ref<HTMLTextAreaElement>(),
  error = ref(""),
  chatError = ref(""),
  draft = ref("");
const side = ref<"attack" | "defense">("attack"),
  title = ref(""),
  persona = ref(""),
  difficulty = ref(1),
  log = ref<HTMLElement>();
const levels = computed(
  () =>
    personas.value.find((p) => p.id === persona.value)
      ?.available_difficulties || [1, 2, 3],
);
const {
  selectedId,
  selected: selectedAnalysis,
  selectedMessage,
  error: analysisError,
  open: analysisOpen,
  inspect,
  retry: retryAnalysis,
  refresh: refreshAnalysis,
} = useAnalysis(messages, () => chat.value?.id);
const {
  suggestion,
  suggesting,
  suggestionError,
  suggest,
  reset: resetSuggestion,
} = useSuggestions();
watch([side, title, persona, difficulty, showCreate], resetSuggestion);
function suggestTopic() {
  if (!debate.value || suggesting.value) return;
  void suggest(debate.value.id, {
    side: side.value,
    title: title.value,
    difficulty: difficulty.value,
    ...(persona.value ? { opponent_persona_id: persona.value } : {}),
  });
}
watch(levels, (v) => {
  if (!v.includes(difficulty.value)) difficulty.value = v[0] || 1;
});
const blocked = computed(() =>
  messages.value.some((m) =>
    ["pending", "generating"].includes(m.generation_status),
  ),
);
let controller: AbortController | undefined,
  timer: ReturnType<typeof setTimeout> | undefined,
  version = 0;
const pendingTurns = new Map<
  string,
  { chat: string; content: string; key: string }
>();
let pending: { chat: string; content: string; key: string } | undefined;
const drafts = new Map<string, string>();
function openCreate(direction: "attack" | "defense") {
  if (creating.value) return;
  createError.value = "";
  showCreate.value = true;
  side.value = direction;
}
function stop() {
  controller?.abort();
  clearTimeout(timer);
  version++;
  sending.value = false;
}
onBeforeUnmount(stop);
async function load() {
  stop();
  const current = version;
  loading.value = true;
  error.value = "";
  debate.value = undefined;
  chat.value = undefined;
  try {
    const [d, p] = await Promise.all([
      request<Debate>(`/debates/${route.params.id}`),
      request<Persona[]>("/topics/opponents"),
    ]);
    if (current !== version) return;
    debate.value = d;
    personas.value = p;
    persona.value = p[0]?.id || "";
    if (route.params.chatId) await selectChat(String(route.params.chatId));
  } catch (e) {
    if (current === version) error.value = failure(e);
  } finally {
    if (current === version || debate.value) loading.value = false;
  }
}
async function selectChat(id: string) {
  if (chat.value) drafts.set(chat.value.id, draft.value);
  stop();
  const current = version;
  historyLoading.value = true;
  messages.value = [];
  chatError.value = "";

  pending = pendingTurns.get(id);
  draft.value = drafts.get(id) || pending?.content || "";
  composerOpen.value = false;
  try {
    const [c, m] = await Promise.all([
      request<Chat>(`/chats/${id}`),
      allPages<Message>(`/chats/${id}/messages`),
    ]);
    if (current !== version) return;
    if (c.debate_id !== debate.value?.id)
      throw new Error("Чат не относится к этим дебатам.");
    chat.value = c;
    messages.value = m;
    if (
      pending?.chat === id &&
      m.some((item) => item.client_request_id === pending?.key)
    ) {
      pendingTurns.delete(id);
      pending = undefined;
      draft.value = "";
    }
    scroll(true);
    poll();
  } catch (e) {
    if (current === version) chatError.value = failure(e);
  } finally {
    if (current === version) historyLoading.value = false;
  }
}
function scroll(force = false) {
  const el = log.value;
  const nearBottom =
    !el || el.scrollHeight - el.scrollTop - el.clientHeight < 100;
  if (force || nearBottom)
    void nextTick(() => {
      if (log.value) log.value.scrollTop = log.value.scrollHeight;
    });
}
async function refresh() {
  if (!chat.value) return;
  const id = chat.value.id,
    current = version;
  try {
    const m = await allPages<Message>(`/chats/${id}/messages`);
    if (current !== version) return;
    messages.value = m;
    if (
      pending?.chat === id &&
      m.some((item) => item.client_request_id === pending?.key)
    ) {
      pendingTurns.delete(id);
      pending = undefined;
      draft.value = "";
    }
    poll();
  } catch (e) {
    if (current === version) {
      chatError.value = failure(e);
      if (e instanceof ApiError && (e.status === 0 || e.status >= 500)) {
        clearTimeout(timer);
        timer = setTimeout(() => {
          void refresh();
        }, 4000);
      }
    }
  }
}
function poll() {
  clearTimeout(timer);
  if (blocked.value && !sending.value)
    timer = setTimeout(() => {
      void refresh();
    }, 4000);
}
async function createChat() {
  if (!debate.value) return;
  creating.value = true;
  createError.value = "";
  try {
    const c = await post<Chat>(`/debates/${debate.value.id}/chats`, {
      side: side.value,
      title: title.value.trim(),
      ...(suggestion.value ? { accepted_suggestion: suggestion.value } : {}),
      difficulty: difficulty.value,
      ...(persona.value ? { opponent_persona_id: persona.value } : {}),
    });
    debate.value.chats?.push(c);
    showCreate.value = false;
    title.value = "";
    await router.push(`/debates/${debate.value.id}/chats/${c.id}`);
  } catch (e) {
    createError.value = failure(e);
  } finally {
    creating.value = false;
  }
}
async function send() {
  if (
    !chat.value ||
    historyLoading.value ||
    chat.value.id !== route.params.chatId ||
    sending.value ||
    blocked.value ||
    !draft.value.trim()
  )
    return;
  const id = chat.value.id,
    content = draft.value.trim(),
    current = version;
  if (pending && (pending.chat !== id || pending.content !== content)) {
    chatError.value =
      "Результат предыдущей отправки неизвестен. Повторите исходный аргумент — дубликат не появится.";
    return;
  }
  pending ??= { chat: id, content, key: crypto.randomUUID() };
  pendingTurns.set(id, pending);
  controller = new AbortController();
  sending.value = true;
  chatError.value = "";
  let responseId = "",
    ended = false;
  try {
    await sendTurn(
      id,
      content,
      pending.key,
      controller.signal,
      (event, data) => {
        if (current !== version) return;
        if (event === "message_started") {
          mergeMessage(messages.value, data.user_message);
          mergeMessage(messages.value, data.response);
          responseId = data.response.id;
          draft.value = "";
          composerOpen.value = false;
          drafts.delete(id);
          pendingTurns.delete(id);
          pending = undefined;
        }
        if (event === "delta") {
          const message = messages.value.find((m) => m.id === responseId);
          if (message) message.content += data.content;
        }
        if (event === "message_completed" || event === "message_status") {
          mergeMessage(messages.value, data);
          ended = true;
        }
        if (event === "error") {
          ended = true;
          chatError.value =
            "Ответ не завершён. Частичный текст сохранён. Можно отправить новый аргумент.";
        }
        scroll();
      },
    );
    if (!ended)
      throw new Error("Соединение прервано. Восстанавливаем историю.");
  } catch (e) {
    if (current === version) {
      chatError.value = failure(e);
      if (e instanceof ApiError && e.status >= 400 && e.status < 500) {
        pendingTurns.delete(id);
        pending = undefined;
      }
    }
  } finally {
    if (current === version) {
      sending.value = false;
      await refresh();
      try {
        const c = await request<Chat>(`/chats/${id}`);
        if (current === version) {
          chat.value = c;
          const i = debate.value?.chats?.findIndex((item) => item.id === id);
          if (i !== undefined && i >= 0) debate.value!.chats![i] = c;
        }
      } catch {
        /* The next workspace reload restores the generated title. */
      }
    }
  }
}
watch(composerOpen, async (value) => {
  if (value) {
    await nextTick();
    argumentInput.value?.focus({ preventScroll: true });
  }
});
watch(() => route.params.id, load, { immediate: true });
watch(
  () => route.params.chatId,
  (id) => {
    if (debate.value) {
      if (id) void selectChat(String(id));
      else {
        stop();
        chat.value = undefined;
      }
    }
  },
);
</script>
<template>
  <main class="debate-page workspace">
    <p v-if="loading" class="empty-state" role="status">Открываем дебаты…</p>
    <p v-if="error" class="error-message" role="alert">
      {{ error }} <button v-if="!debate" @click="load">Повторить</button>
    </p>
    <template v-if="debate"
      ><header class="workspace-heading">
        <h1>{{ debate.topic_title }}</h1>
        <LiquidDisclosure title="Позиции сторон" class="positions">
          <div class="position-layers">
            <GlassPanel inset
              ><h3>Ваша позиция</h3>
              <p>{{ debate.user_position }}</p></GlassPanel
            ><GlassPanel inset
              ><h3>Позиция оппонента</h3>
              <p>{{ debate.opponent_position }}</p></GlassPanel
            >
          </div>
        </LiquidDisclosure>
      </header>
      <GlassDialog
        v-model="showCreate"
        :title="
          side === 'attack' ? 'Новая подтема атаки' : 'Новая подтема защиты'
        "
        :busy="creating"
      >
        <form class="chat-create debate-form" @submit.prevent="createChat">
          <fieldset :disabled="creating || suggesting">
            <legend class="sr-only">
              Новая подтема
              {{ side === "attack" ? "атаки" : "защиты" }}
            </legend>
            <div class="suggest-input-row">
              <label
                >{{
                  side === "defense"
                    ? "Тезис, который защищает ИИ"
                    : "Направление аргумента"
                }}<input
                  v-model="title"
                  class="text-input"
                  :required="side === 'defense' && !suggestion"
                  maxlength="300"
              /></label>
              <span class="suggest-tooltip-anchor"
                ><button
                  type="button"
                  class="icon-button"
                  aria-label="Предложить тему с помощью ИИ"
                  aria-describedby="suggest-tooltip"
                  @click="suggestTopic"
                >
                  <WandSparkles :size="20" /></button
                ><span
                  id="suggest-tooltip"
                  class="suggest-tooltip"
                  role="tooltip"
                  >ИИ предложит тему. Вы сможете выбрать другой вариант перед
                  созданием чата.</span
                ></span
              >
            </div>
            <p v-if="side === 'attack'" class="muted">
              Можно начать с аргумента без названия.
            </p>
            <label
              >Оппонент<select v-model="persona" class="text-input">
                <option v-if="!personas.length" value="">По умолчанию</option>
                <option v-for="p in personas" :key="p.id" :value="p.id">
                  {{ p.name }}
                </option>
              </select></label
            ><label
              >Сложность<select v-model="difficulty" class="text-input">
                <option v-for="n in levels" :key="n" :value="n">
                  {{ n }}
                </option>
              </select></label
            >
          </fieldset>
          <p v-if="suggesting" role="status" class="muted">
            Подбираем направление…
          </p>
          <section
            v-if="suggestion"
            class="suggest-preview"
            aria-label="Предложение ИИ"
          >
            <h3>{{ suggestion.title }}</h3>
            <p>{{ suggestion.description }}</p>
            <p>
              {{ side === "attack" ? suggestion.hint : suggestion.seed_claim }}
            </p>
            <div class="suggest-actions">
              <button
                type="button"
                class="text-action"
                :disabled="suggesting || creating"
                @click="suggestTopic"
              >
                <RotateCw :size="16" /> Другой вариант</button
              ><button
                type="button"
                class="text-action"
                :disabled="suggesting || creating"
                @click="resetSuggestion"
              >
                Написать самостоятельно
              </button>
            </div>
          </section>
          <p v-if="suggestionError" class="error-message" role="alert">
            {{ suggestionError }}
          </p>
          <AppButton
            class="chat-create-submit"
            type="submit"
            :busy="creating"
            :disabled="suggesting"
            >{{
              suggestion ? "Принять и начать диалог" : "Создать чат"
            }}</AppButton
          >
        </form>
        <p v-if="createError" class="error-message" role="alert">
          {{ createError }}
        </p></GlassDialog
      >
      <div
        class="workspace-grid"
        :class="{ 'workspace-grid--analysis': selectedId && !historyLoading }"
      >
        <GlassPanel class="chat-sidebar"
          ><div class="chat-sidebar-scroll">
            <h2>Подтемы</h2>
            <section
              v-for="direction in ['defense', 'attack'] as const"
              :key="direction"
              class="chat-group glass-panel glass-panel--inset"
            >
              <header class="chat-group-header">
                <h3>{{ direction === "attack" ? "Атака" : "Защита" }}</h3>
                <button
                  class="icon-button add-chat"
                  :aria-label="
                    direction === 'attack'
                      ? 'Добавить подтему атаки'
                      : 'Добавить подтему защиты'
                  "
                  :aria-expanded="showCreate && side === direction"
                  :disabled="creating"
                  @click="openCreate(direction)"
                >
                  <Plus
                    :size="18"
                    :class="{ 'plus-open': showCreate && side === direction }"
                  />
                </button>
              </header>
              <RouterLink
                v-for="c in debate.chats?.filter((c) => c.side === direction)"
                :key="c.id"
                :to="`/debates/${debate.id}/chats/${c.id}`"
                class="chat-link"
                :title="c.title || 'Новый аргумент'"
                :aria-current="
                  route.params.chatId === c.id ? 'page' : undefined
                "
                >{{ c.title || "Новый аргумент" }}</RouterLink
              >
              <p
                v-if="!debate.chats?.some((c) => c.side === direction)"
                class="muted"
              >
                Пока нет подтем
              </p>
            </section>
          </div></GlassPanel
        >
        <GlassPanel class="conversation" :aria-busy="historyLoading">
          <p v-if="historyLoading" class="chat-loading" role="status">
            Загружаем историю…
          </p>
          <template v-if="chat"
            ><header class="conversation-header">
              <h2>{{ chat.title || "Новый аргумент" }}</h2>
              <p class="muted">
                {{ chat.side === "attack" ? "Атака" : "Защита" }} ·
                {{
                  personas.find((p) => p.id === chat?.opponent_persona_id)
                    ?.name || "Оппонент"
                }}
                · Сложность {{ chat.difficulty }}
              </p>
            </header>
            <div
              ref="log"
              class="message-list"
              role="log"
              aria-label="Сообщения"
              tabindex="0"
              :class="{ 'history-switching': historyLoading }"
            >
              <aside v-if="chat.attack_hint" class="attack-hint">
                <h3><WandSparkles :size="16" /> Подсказка ИИ</h3>
                <p>{{ chat.attack_hint }}</p>
              </aside>
              <p
                v-if="!messages.length && !chat.attack_hint"
                class="empty-state"
              >
                Сформулируйте первый аргумент.
              </p>
              <article
                v-for="m in messages"
                :key="m.id"
                class="message"
                :class="{ 'message-user': m.role === 'user' }"
              >
                <header class="message-heading">
                  <h3>{{ m.role === "user" ? "Вы" : "Оппонент" }}</h3>
                  <button
                    v-if="m.role === 'user'"
                    class="icon-button message-analysis-button"
                    aria-label="Посмотреть анализ этого ответа"
                    @click="inspect(m.id)"
                  >
                    <CircleHelp :size="18" />
                  </button>
                </header>
                <MessageContent
                  v-if="m.role === 'assistant'"
                  :content="
                    m.content ||
                    (m.generation_status === 'generating'
                      ? 'Формулирует ответ…'
                      : 'Ответ не получен')
                  "
                />
                <p v-else>{{ m.content }}</p>
                <span
                  v-if="m.generation_status === 'failed'"
                  class="message-state"
                  >Ответ не завершён</span
                >
              </article>
            </div>
            <p v-if="chatError" class="error-message" role="alert">
              {{ chatError }}
            </p>
            <div v-if="sending || blocked" class="conversation-status">
              <span v-if="sending" role="status">Оппонент отвечает…</span
              ><span v-else-if="blocked" role="status"
                >Ответ ещё готовится. Проверяем историю…</span
              >
            </div>
            <button
              v-if="pending?.chat === chat.id && !sending"
              class="text-action"
              @click="
                draft = pending?.content || draft;
                composerOpen = true;
              "
            >
              Восстановить исходный аргумент для безопасного повтора
            </button>
            <LiquidDisclosure
              v-model="composerOpen"
              title="Ваш аргумент"
              :summary="draft.trim() ? 'Черновик' : 'Написать'"
              class="composer-disclosure"
              ><form class="composer" @submit.prevent="send">
                <label for="argument">Ваш аргумент</label
                ><textarea
                  id="argument"
                  ref="argumentInput"
                  v-model="draft"
                  class="text-input"
                  rows="4"
                  required
                  maxlength="12000"
                  :disabled="
                    historyLoading ||
                    sending ||
                    blocked ||
                    ['completed', 'closed', 'archived'].includes(chat.status)
                  "
                />
                <div>
                  <span class="muted">{{ draft.length }} / 12000</span
                  ><AppButton
                    type="submit"
                    :busy="sending"
                    :disabled="
                      historyLoading ||
                      !draft.trim() ||
                      blocked ||
                      ['completed', 'closed', 'archived'].includes(chat.status)
                    "
                    >Отправить</AppButton
                  >
                </div>
                <p
                  v-if="
                    ['completed', 'closed', 'archived'].includes(chat.status)
                  "
                  class="muted"
                >
                  Этот чат закрыт.
                </p>
              </form></LiquidDisclosure
            >
          </template>
          <div v-else class="empty-state">
            <h2>Выберите подтему</h2>
            <p>Продолжите защиту своей позиции или создайте чат атаки.</p>
            <p v-if="chatError" class="error-message" role="alert">
              {{ chatError }}
            </p>
          </div></GlassPanel
        >
        <AnalysisPanel
          v-if="selectedId && !historyLoading"
          v-model:open="analysisOpen"
          :analysis="selectedAnalysis"
          :content="selectedMessage?.content"
          :error="analysisError"
          @retry="retryAnalysis"
          @refresh="refreshAnalysis"
        /></div
    ></template>
  </main>
</template>
