import { describe, it, expect } from "vitest";
import { readEvents } from "./debates";
describe("SSE transport", () => {
  it("decodes fragmented UTF-8 and CRLF frames", async () => {
    const bytes = new TextEncoder().encode(
      'event: delta\r\ndata: {"content":"Привет"}\r\n\r\nevent: message_completed\ndata: {"id":"m"}\n\n',
    );
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        for (const b of bytes) c.enqueue(new Uint8Array([b]));
        c.close();
      },
    });
    const events: unknown[] = [];
    await readEvents(stream, (event, data) => events.push([event, data]));
    expect(events).toEqual([
      ["delta", { content: "Привет" }],
      ["message_completed", { id: "m" }],
    ]);
  });
  it("rejects an incomplete frame so history can be restored", async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(new TextEncoder().encode("event: delta\ndata: {"));
        c.close();
      },
    });
    await expect(readEvents(stream, () => {})).rejects.toThrow("оборвался");
  });
});
