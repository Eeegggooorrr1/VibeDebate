import { nextTick, onMounted, ref, type Ref } from "vue";

export function useLiquidDisclosure(
  shell: Ref<HTMLElement | null>,
  content: Ref<HTMLElement | null>,
  header: Ref<HTMLElement | null>,
  initial: boolean,
) {
  const expanded = ref(initial);
  let animation: Animation | undefined;
  let observer: ResizeObserver | undefined;
  let revision = 0;
  async function toggle() {
    const el = shell.value;
    if (!el || !content.value || !header.value) return;
    const from = el.getBoundingClientRect().height;
    animation?.cancel();
    expanded.value = !expanded.value;
    const current = ++revision;
    await nextTick();
    if (current !== revision) return;
    const to =
      header.value.offsetHeight +
      (expanded.value ? content.value.scrollHeight : 0);
    el.style.height = `${to}px`;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      if (expanded.value) el.style.height = "auto";
      return;
    }
    animation = el.animate([{ height: `${from}px` }, { height: `${to}px` }], {
      duration: expanded.value ? 440 : 280,
      easing: expanded.value
        ? "cubic-bezier(.2,1.18,.35,1)"
        : "cubic-bezier(.2,.8,.3,1)",
    });
    animation.onfinish = () => {
      if (expanded.value && current === revision) el.style.height = "auto";
    };
  }
  onMounted(() => {
    if (shell.value && header.value)
      shell.value.style.height = initial
        ? "auto"
        : `${header.value.offsetHeight}px`;
    observer = new ResizeObserver(() => {
      if (!expanded.value && shell.value && header.value)
        shell.value.style.height = `${header.value.offsetHeight}px`;
    });
    if (header.value) observer.observe(header.value);
  });
  return {
    expanded,
    toggle,
    dispose: () => {
      revision++;
      animation?.cancel();
      observer?.disconnect();
    },
  };
}
