<script lang="ts">
import { computed, defineComponent, h } from "vue";
// Render text as Vue nodes: model output can never introduce executable HTML.
export default defineComponent({
  props: { content: { type: String, required: true } },
  setup(props) {
    function inline(text: string) {
      return text
        .split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g)
        .map((part) =>
          part.startsWith("**") && part.endsWith("**")
            ? h("strong", part.slice(2, -2))
            : part.startsWith("`") && part.endsWith("`")
              ? h("code", part.slice(1, -1))
              : part.startsWith("*") && part.endsWith("*")
                ? h("em", part.slice(1, -1))
                : part,
        );
    }
    const blocks = computed(() => {
      const lines = props.content.split("\n");
      const nodes = [];
      let code: string[] | null = null;
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i] || "";
        if (line.startsWith("```")) {
          if (code) {
            nodes.push(h("pre", h("code", code.join("\n"))));
            code = null;
          } else code = [];
          continue;
        }
        if (code) {
          code.push(line);
          continue;
        }
        if (!line.trim()) continue;
        const list = line.match(/^\s*(?:[-*]|\d+[.)])\s+(.*)/);
        if (list) {
          const ordered = /^\s*\d/.test(line);
          const items = [h("li", inline(list[1] || ""))];
          while (i + 1 < lines.length) {
            const next = (lines[i + 1] || "").match(
              ordered ? /^\s*\d+[.)]\s+(.*)/ : /^\s*[-*]\s+(.*)/,
            );
            if (!next) break;
            items.push(h("li", inline(next[1] || "")));
            i++;
          }
          nodes.push(h(ordered ? "ol" : "ul", items));
        } else if (/^#{1,6}\s/.test(line))
          nodes.push(h("h4", inline(line.replace(/^#{1,6}\s+/, ""))));
        else if (line.startsWith("> "))
          nodes.push(h("blockquote", inline(line.slice(2))));
        else nodes.push(h("p", inline(line)));
      }
      if (code) nodes.push(h("pre", h("code", code.join("\n"))));
      return nodes;
    });
    return () => h("div", { class: "message-rich" }, blocks.value);
  },
});
</script>
