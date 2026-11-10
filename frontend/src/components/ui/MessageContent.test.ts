import { describe, it, expect } from "vitest";
import { createSSRApp } from "vue";
import { renderToString } from "vue/server-renderer";
import MessageContent from "./MessageContent.vue";
describe("AI message formatting", () => {
  it("renders emphasis and lists while escaping raw model HTML", async () => {
    const html = await renderToString(
      createSSRApp(MessageContent, {
        content:
          "**Тезис** и *уточнение*\n\n- Основание\n- Вывод\n<img src=x onerror=alert(1)>",
      }),
    );
    expect(html).toContain("<strong>Тезис</strong>");
    expect(html).toContain("<em>уточнение</em>");
    expect(html).toContain("<ul><li>Основание</li><li>Вывод</li></ul>");
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img");
  });
});
