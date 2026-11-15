<script setup lang="ts">
import { computed, watch, onBeforeUnmount } from "vue";
import GlassDialog from "../ui/GlassDialog.vue";
import AppButton from "../ui/AppButton.vue";
import { useExercises } from "../../features/debates/useExercises";
const props = defineProps<{
  open: boolean;
  messageId: string;
  issueIndex: number;
}>();
const emit = defineEmits<{ "update:open": [boolean] }>();
const {
  exercise,
  busy,
  error,
  answer,
  order,
  choice,
  feedback,
  history,
  load,
  check,
  save,
  stop,
} = useExercises();
const kind = computed(() => exercise.value?.kind);
function start(fresh = false) {
  void load(props.messageId, props.issueIndex, fresh);
}
watch(
  () => [props.open, props.messageId, props.issueIndex],
  () => {
    if (props.open) start();
    else stop();
  },
);
onBeforeUnmount(stop);
function move(i: number, delta: number) {
  const values = [...order.value];
  [values[i], values[i + delta]] = [values[i + delta]!, values[i]!];
  order.value = values;
  save();
}
</script>
<template>
  <GlassDialog
    :model-value="open"
    title="Тренировка аргументации"
    fullscreen
    @update:model-value="emit('update:open', $event)"
  >
    <div class="exercise-workspace">
      <p v-if="busy" role="status">
        {{ exercise ? "Проверяем ответ…" : "Готовим упражнение…" }}
      </p>
      <p v-if="error" role="alert" class="error-message">
        {{ error }}
        <button v-if="!exercise" class="text-action" @click="start(true)">
          Повторить
        </button>
      </p>
      <template v-if="exercise">
        <section class="exercise-task">
          <h3>{{ exercise.title }}</h3>
          <p class="exercise-instruction">{{ exercise.instruction }}</p>
        </section>
        <form class="exercise-solution" @submit.prevent="check">
          <h3>Ваше решение</h3>
          <fieldset
            :disabled="
              busy || (!!feedback && (kind === 'quiz' || kind === 'order'))
            "
          >
            <legend class="sr-only">Ваше решение</legend>
            <template v-if="kind === 'quiz'"
              ><label
                v-for="(item, i) in exercise.items"
                :key="i"
                class="exercise-option"
                ><input
                  v-model="choice"
                  type="radio"
                  name="exercise-choice"
                  :value="i"
                  @change="save"
                />{{ item }}</label
              ></template
            >
            <ol v-else-if="kind === 'order'" class="exercise-order">
              <li v-for="(item, i) in order" :key="item">
                <p>{{ exercise.items[item] }}</p>
                <div>
                  <button
                    type="button"
                    :disabled="i === 0"
                    :aria-label="`Переместить шаг ${i + 1} выше`"
                    @click="move(i, -1)"
                  >
                    Выше</button
                  ><button
                    type="button"
                    :disabled="i === order.length - 1"
                    :aria-label="`Переместить шаг ${i + 1} ниже`"
                    @click="move(i, 1)"
                  >
                    Ниже
                  </button>
                </div>
              </li>
            </ol>
            <template v-else>
              <article
                v-for="(turn, i) in history"
                :key="i"
                class="exercise-turn"
              >
                <h4>Попытка {{ i + 1 }}</h4>
                <p class="exercise-user-answer">{{ turn.answer }}</p>
                <h4>Обратная связь</h4>
                <p>{{ turn.feedback }}</p>
              </article>
              <label v-if="!feedback?.achieved && history.length < 3"
                >Ваш ответ<textarea
                  v-model="answer"
                  class="text-input"
                  rows="5"
                  maxlength="4000"
                  @input="save"
                />
              </label>
            </template>
          </fieldset>
          <AppButton
            v-if="
              !feedback ||
              (kind !== 'quiz' &&
                kind !== 'order' &&
                !feedback.achieved &&
                history.length < 3)
            "
            type="submit"
            :busy="busy"
            :disabled="
              kind === 'quiz' ? choice < 0 : kind !== 'order' && !answer.trim()
            "
            >Проверить</AppButton
          >
        </form>
        <section v-if="feedback" class="exercise-feedback" aria-live="polite">
          <h3>
            {{
              feedback.achieved
                ? "Цель достигнута"
                : history.length >= 3
                  ? "Тренировка завершена"
                  : "Есть что улучшить"
            }}
          </h3>
          <p v-if="kind === 'quiz' || kind === 'order'">
            {{ feedback.feedback }}
          </p>
          <template v-if="kind === 'order'">
            <p>Правильная последовательность:</p>
            <ol>
              <li v-for="i in exercise.solution" :key="i">
                {{ exercise.items[i] }}
              </li>
            </ol>
          </template>
        </section>
        <footer class="exercise-actions">
          <button class="text-action" :disabled="busy" @click="start(true)">
            Другое упражнение по этой ошибке
          </button>
        </footer>
      </template>
    </div>
  </GlassDialog>
</template>
