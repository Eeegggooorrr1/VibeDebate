<script setup lang="ts">
import { computed, useId } from "vue";
import type { Chat } from "../../api/debate-contracts";
const props = defineProps<{ chat: Chat; compact?: boolean }>();
const id = useId();
// An actual zero score is an assessment; no scored answers is a separate state.
const hasAssessment = computed(() => (props.chat.scored_answers || 0) > 0);
const hasStatus = computed(
  () => hasAssessment.value || !!props.chat.mastered_at,
);
const value = computed(() => props.chat.progress || 0);
const expression = computed(() =>
  props.chat.mastered_at || value.value >= 80
    ? "happy"
    : value.value >= 40
      ? "neutral"
      : "sad",
);
const average = computed(() =>
  hasAssessment.value
    ? ((props.chat.score_total || 0) / props.chat.scored_answers!).toFixed(1)
    : "—",
);
const description = computed(() =>
  !hasStatus.value
    ? "Пока нет оценки"
    : props.chat.mastered_at
      ? "Чат пройден"
      : `Прогресс ${value.value}%. Средний балл ${average.value}. Хороших ответов подряд: ${props.chat.good_streak || 0} из 3`,
);
</script>
<template>
  <span
    :class="[
      'chat-progress',
      {
        'chat-progress--unrated': !hasStatus,
        'chat-progress--compact': compact,
      },
    ]"
    :title="description"
  >
    <svg
      viewBox="16 16 96 96"
      width="30"
      height="30"
      role="img"
      :aria-label="description"
    >
      <defs>
        <linearGradient :id="`${id}-fill`" x1="0" y1="0" x2="0.7" y2="1">
          <stop :stop-color="hasStatus ? '#72513b' : '#5b5753'" />
          <stop offset="0.48" :stop-color="hasStatus ? '#473326' : '#403c38'" />
          <stop offset="1" :stop-color="hasStatus ? '#30251e' : '#302d2a'" />
        </linearGradient>
        <linearGradient :id="`${id}-edge`" x1="0" y1="0" x2="0.6" y2="1">
          <stop
            :stop-color="hasStatus ? '#ebc4a1' : '#a59f98'"
            stop-opacity="0.75"
          />
          <stop
            offset="1"
            :stop-color="hasStatus ? '#a16b45' : '#77716b'"
            stop-opacity="0.12"
          />
        </linearGradient>
      </defs>
      <circle
        cx="64"
        cy="64"
        r="47"
        :fill="`url(#${id}-fill)`"
        :stroke="`url(#${id}-edge)`"
        stroke-width="2"
      />
      <g
        v-if="hasStatus"
        fill="none"
        stroke="#efceaf"
        stroke-width="3.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path v-if="chat.mastered_at" d="m43 64 14 14 29-30" />
        <template v-else>
          <path d="M49 49v5m30-5v5" />
          <path
            :d="
              expression === 'happy'
                ? 'M45 71c8 16 30 16 38 0'
                : expression === 'neutral'
                  ? 'M47 79h34'
                  : 'M47 85c8-15 26-15 34 0'
            "
          />
        </template>
      </g>
    </svg>
    <span v-if="!compact" class="chat-progress-details">
      <strong>{{
        !hasStatus
          ? "Пока нет оценки"
          : chat.mastered_at
            ? "Чат пройден"
            : `Прогресс ${value}%`
      }}</strong>
      <span v-if="chat.mastery_source === 'opponent_concession'"
        >Оппонент признал победу</span
      >
      <template v-if="hasStatus">
        <span
          >Средний балл {{ average }} · Ответов {{ chat.scored_answers }} ·
          Серия {{ chat.good_streak || 0 }}</span
        >
        <span
          class="chat-progress-track"
          role="progressbar"
          :aria-valuenow="value"
          aria-valuemin="0"
          aria-valuemax="100"
          aria-label="Прогресс чата"
          ><span :style="{ width: `${value}%` }"
        /></span>
      </template>
    </span>
  </span>
</template>
