import { onBeforeUnmount, ref } from "vue";
import { post, failure } from "../../api/debates";
import type { ChatSuggestion } from "../../api/debate-contracts";

export function useSuggestions() {
  const suggestion = ref<ChatSuggestion>();
  const suggesting = ref(false);
  const suggestionError = ref("");
  let version = 0;
  let previous: string[] = [];
  function reset() {
    version++;
    suggestion.value = undefined;
    suggesting.value = false;
    suggestionError.value = "";
    previous = [];
  }
  async function suggest(debateId: string, input: Record<string, unknown>) {
    const current = ++version;
    suggesting.value = true;
    suggestionError.value = "";
    try {
      const result = await post<ChatSuggestion>(
        `/debates/${debateId}/chat-suggestions`,
        {
          ...input,
          previous_titles: previous.slice(-10),
        },
      );
      if (current !== version) return;
      suggestion.value = result;
      previous.push(result.title);
    } catch (e) {
      if (current === version) suggestionError.value = failure(e);
    } finally {
      if (current === version) suggesting.value = false;
    }
  }
  onBeforeUnmount(reset);
  return { suggestion, suggesting, suggestionError, suggest, reset };
}
