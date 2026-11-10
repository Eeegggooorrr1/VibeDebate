<script setup lang="ts">
import { computed } from "vue";
import {
  CircleAlert,
  TriangleAlert,
  Pencil,
  Check,
  LoaderCircle,
  ArrowUpRight,
} from "@lucide/vue";
import GlassPanel from "../ui/GlassPanel.vue";
import GlassDialog from "../ui/GlassDialog.vue";
import type { MessageAnalysis } from "../../api/debate-contracts";
const props = defineProps<{
  analysis?: MessageAnalysis;
  content?: string;
  open: boolean;
  error: string;
}>();
const emit = defineEmits<{
  "update:open": [value: boolean];
  retry: [];
  refresh: [];
}>();
const busy = computed(
  () =>
    !props.analysis || ["pending", "running"].includes(props.analysis.status),
);
const severities = [
  { key: "high", label: "Серьёзные", icon: CircleAlert },
  { key: "medium", label: "Замечания", icon: TriangleAlert },
  { key: "low", label: "Уточнения", icon: Pencil },
] as const;
const dimensions: Record<string, string> = {
  claim_clarity: "Ясность тезиса",
  relevance: "Релевантность",
  logical_validity: "Логика",
  evidence_quality: "Качество оснований",
  factual_accuracy: "Точность фактов",
  conceptual_precision: "Точность понятий",
  counterargument_handling: "Работа с возражением",
  calibration: "Обоснованность уверенности",
};
</script>
<template>
  <GlassPanel class="analysis-panel">
    <button
      class="analysis-preview"
      aria-label="Открыть подробный анализ ответа"
      @click="emit('update:open', true)"
    >
      <span class="analysis-preview-heading"
        >Анализ ответа <ArrowUpRight :size="18"
      /></span>
      <span v-if="error" class="muted">Не удалось загрузить разбор</span>
      <span v-else-if="busy" class="analysis-loading" role="status"
        ><LoaderCircle :size="18" /> Анализируем…</span
      >
      <span v-else-if="analysis?.status === 'failed'">Разбор не завершён</span>
      <template v-else-if="analysis">
        <span class="analysis-counts">
          <span
            v-for="s in severities"
            :key="s.key"
            :class="['analysis-count', `severity-${s.key}`]"
            :title="s.label"
          >
            <component :is="s.icon" :size="17" />
            {{ analysis.issues.filter((i) => i.severity === s.key).length }}
            <span class="sr-only">{{ s.label }}</span>
          </span>
        </span>
        <span v-if="!analysis.is_substantive" class="muted"
          >Нет аргумента для оценки</span
        >
        <span v-else-if="!analysis.issues.length" class="analysis-loading"
          ><Check :size="16" /> Замечаний нет</span
        >
        <span v-if="analysis.overall_score !== null" class="muted"
          >{{ analysis.overall_score }} / 100</span
        >
      </template>
    </button>
  </GlassPanel>
  <GlassDialog
    :model-value="open"
    title="Разбор ответа"
    fullscreen
    @update:model-value="emit('update:open', $event)"
  >
    <div class="analysis-detail">
      <section v-if="content">
        <h3>Ваш ответ</h3>
        <blockquote>{{ content }}</blockquote>
      </section>
      <p v-if="error" class="error-message" role="alert">
        {{ error }}
        <button class="text-action" @click="emit('refresh')">
          Повторить загрузку
        </button>
      </p>
      <p v-else-if="busy" class="analysis-loading" role="status">
        <LoaderCircle :size="20" /> Анализируем аргумент…
      </p>
      <div v-else-if="analysis?.status === 'failed'">
        <p>Не удалось завершить разбор. Ваш ответ сохранён.</p>
        <button class="text-action" @click="emit('retry')">
          Повторить анализ
        </button>
      </div>
      <template v-else-if="analysis">
        <p v-if="!analysis.is_substantive">
          В этом сообщении нет содержательного аргумента для оценки.
        </p>
        <p v-else-if="analysis.overall_score !== null" class="analysis-score">
          Оценка аргумента: <strong>{{ analysis.overall_score }} / 100</strong>
        </p>
        <section v-if="analysis.strengths.length">
          <h3>Что получилось</h3>
          <ul>
            <li v-for="s in analysis.strengths" :key="s">{{ s }}</li>
          </ul>
        </section>
        <section>
          <h3>
            Замечания <span class="muted">{{ analysis.issues.length }}</span>
          </h3>
          <p v-if="!analysis.issues.length">Замечаний не найдено.</p>
          <article
            v-for="(issue, index) in analysis.issues"
            :key="index"
            class="analysis-issue"
          >
            <h4>
              <span :class="['analysis-count', `severity-${issue.severity}`]"
                ><component
                  :is="severities.find((s) => s.key === issue.severity)?.icon"
                  :size="18"
              /></span>
              {{ severities.find((s) => s.key === issue.severity)?.label }}
            </h4>
            <blockquote>{{ issue.evidence_quote }}</blockquote>
            <p>{{ issue.explanation }}</p>
            <p><strong>Как улучшить:</strong> {{ issue.improvement }}</p>
          </article>
        </section>
        <section v-if="analysis.next_step">
          <h3>Следующий шаг</h3>
          <p>{{ analysis.next_step }}</p>
        </section>
        <section v-if="analysis.conduct_flags.length">
          <h3>Манера дискуссии</h3>
          <ul>
            <li v-for="flag in analysis.conduct_flags" :key="flag">
              {{ flag }}
            </li>
          </ul>
        </section>
        <section>
          <h3>По критериям</h3>
          <dl class="analysis-dimensions">
            <div v-for="d in analysis.dimensions" :key="d.key">
              <dt>
                {{ dimensions[d.key] || d.key }}
                <span>{{
                  d.applicable ? `${d.score} / 4` : "Не применимо"
                }}</span>
              </dt>
              <dd>{{ d.explanation }}</dd>
            </div>
          </dl>
        </section>
      </template>
    </div>
  </GlassDialog>
</template>
