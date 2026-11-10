import { computed, onBeforeUnmount, ref, watch, type Ref } from "vue";
import { request } from "../../api/http";
import { post, failure } from "../../api/debates";
import type { Message, MessageAnalysis } from "../../api/debate-contracts";

export function useAnalysis(
  messages: Ref<Message[]>,
  chatId: () => string | undefined,
) {
  const results = ref<Record<string, MessageAnalysis>>({});
  const selectedId = ref("");
  const error = ref("");
  const open = ref(false);
  let generation = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let disposed = false;
  const selected = computed(() => results.value[selectedId.value]);
  const selectedMessage = computed(() =>
    messages.value.find((m) => m.id === selectedId.value),
  );

  async function refresh() {
    const run = ++generation;
    clearTimeout(timer);
    const targets = messages.value.filter(
      (m) =>
        m.role === "user" &&
        !["completed", "failed"].includes(results.value[m.id]?.status || ""),
    );
    try {
      // Bound concurrency and keep old chat responses from updating the current view.
      for (const message of targets) {
        const result = await request<MessageAnalysis>(
          `/messages/${message.id}/analysis`,
        );
        if (run !== generation || disposed) return;
        results.value[message.id] = result;
      }
      error.value = "";
    } catch (e) {
      if (run !== generation || disposed) return;
      error.value = failure(e);
    }
    if (run !== generation || disposed) return;
    if (
      messages.value.some(
        (m) =>
          m.role === "user" &&
          !["completed", "failed"].includes(results.value[m.id]?.status || ""),
      )
    )
      timer = setTimeout(() => void refresh(), 2500);
  }
  async function retry() {
    const id = selectedId.value,
      run = generation;
    try {
      const result = await post<MessageAnalysis>(
        `/messages/${id}/analysis/retry`,
        {},
      );
      if (run !== generation || disposed) return;
      results.value[id] = result;
      void refresh();
    } catch (e) {
      if (run === generation) error.value = failure(e);
    }
  }
  function inspect(id: string) {
    selectedId.value = id;
    open.value = true;
  }
  watch(chatId, () => {
    generation++;
    clearTimeout(timer);
    results.value = {};
    selectedId.value = "";
    open.value = false;
    error.value = "";
  });
  watch(
    () => messages.value.map((m) => m.id).join(","),
    () => {
      const users = messages.value.filter((m) => m.role === "user");
      selectedId.value = users.at(-1)?.id || "";
      void refresh();
    },
  );
  onBeforeUnmount(() => {
    disposed = true;
    generation++;
    clearTimeout(timer);
  });
  return {
    results,
    selectedId,
    selected,
    selectedMessage,
    error,
    open,
    inspect,
    retry,
    refresh,
  };
}
