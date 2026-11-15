import { ref } from "vue";
import { post, failure } from "../../api/debates";
export type Kind = "quiz" | "order" | "premise" | "rewrite" | "coach";
export interface Exercise {
  kind: Kind;
  title: string;
  instruction: string;
  items: string[];
  solution: number[];
  explanation: string;
  criteria: string;
}
interface Feedback {
  achieved: boolean;
  feedback: string;
  next_question: string;
}
export function useExercises() {
  const exercise = ref<Exercise>(),
    busy = ref(false),
    error = ref(""),
    answer = ref("");
  const order = ref<number[]>([]),
    choice = ref(-1),
    feedback = ref<Feedback>();
  const history = ref<{ answer: string; feedback: string }[]>([]);
  let version = 0,
    key = "",
    message = "",
    index = 0;
  function save() {
    try {
      const keys = Object.keys(sessionStorage).filter((k) =>
        k.startsWith("exercise-v2:"),
      );
      if (keys.length >= 30 && !sessionStorage.getItem(key))
        sessionStorage.removeItem(keys[0]!);
      sessionStorage.setItem(
        key,
        JSON.stringify({
          at: Date.now(),
          exercise: exercise.value,
          answer: answer.value,
          order: order.value,
          choice: choice.value,
          feedback: feedback.value,
          history: history.value,
        }),
      );
    } catch {
      /* Storage may be disabled; the current exercise remains usable. */
    }
  }
  async function load(id: string, issue: number, fresh = false) {
    const run = ++version;
    message = id;
    index = issue;
    key = `exercise-v2:${id}:${issue}`;
    exercise.value = undefined;
    feedback.value = undefined;
    answer.value = "";
    history.value = [];
    choice.value = -1;
    order.value = [];
    error.value = "";
    busy.value = true;
    if (!fresh)
      try {
        const cached = JSON.parse(sessionStorage.getItem(key) || "null");
        if (
          cached &&
          Date.now() - cached.at < 86400000 &&
          cached.exercise?.kind
        ) {
          exercise.value = cached.exercise;
          answer.value = cached.answer;
          order.value = cached.order;
          choice.value = cached.choice;
          feedback.value = cached.feedback;
          history.value = cached.history;
          busy.value = false;
          return;
        }
      } catch {
        /* Regenerate a damaged cache entry. */
      }
    try {
      const result = await post<Exercise>(`/messages/${id}/exercises`, {
        issue_index: issue,
      });
      if (run !== version) return;
      exercise.value = result;
      order.value = result.items.map((_, i) => i);
      save();
    } catch (e) {
      if (run === version) error.value = failure(e);
    } finally {
      if (run === version) busy.value = false;
    }
  }
  async function check() {
    const e = exercise.value;
    if (!e || busy.value) return;
    error.value = "";
    if (e.kind === "quiz" || e.kind === "order") {
      const actual = e.kind === "quiz" ? [choice.value] : order.value;
      feedback.value = {
        achieved: JSON.stringify(actual) === JSON.stringify(e.solution),
        feedback: e.explanation,
        next_question: "",
      };
      save();
      return;
    }
    if (!answer.value.trim() || history.value.length >= 3) return;
    const run = version,
      submitted = answer.value.trim();
    busy.value = true;
    try {
      const result = await post<Feedback>(
        `/messages/${message}/exercises/check`,
        {
          issue_index: index,
          exercise: e,
          answer: submitted,
          history: history.value,
        },
      );
      if (run !== version) return;
      history.value.push({
        answer: submitted,
        feedback: [result.feedback, result.next_question]
          .filter(Boolean)
          .join("\n\n"),
      });
      feedback.value = result;
      answer.value = "";
      save();
    } catch (err) {
      if (run === version) error.value = failure(err);
    } finally {
      if (run === version) busy.value = false;
    }
  }
  function stop() {
    version++;
    busy.value = false;
  }
  return {
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
  };
}
