import { request, ApiError } from "./http";
import { accessToken, endSession } from "../auth/session";
import { environment } from "../config/environment";
import type { Message } from "./debate-contracts";
export async function allPages<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T[]> {
  const result: T[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await request<T[]>(
      `${path}${path.includes("?") ? "&" : "?"}limit=100&offset=${offset}`,
      { signal },
    );
    result.push(...page);
    if (page.length < 100) return result;
  }
}
export const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });
export const failure = (e: unknown) => {
  if (e instanceof ApiError)
    return (
      (
        {
          chat_busy: "Оппонент ещё отвечает. Дождитесь завершения ответа.",
          ai_not_configured: "Сервис ИИ пока не настроен.",
          context_limit_exceeded:
            "Контекст чата заполнен. Создайте новую подтему.",
          ai_timeout: "Оппонент не ответил вовремя. Попробуйте позже.",
        } as Record<string, string>
      )[e.code] || e.message
    );
  return e instanceof Error ? e.message : "Не удалось выполнить запрос.";
};
export async function readEvents(
  body: ReadableStream<Uint8Array>,
  onEvent: (name: string, data: any) => void,
) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  function drain(final = false) {
    buffer = buffer.replace(/\r\n/g, "\n");
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const lines = frame.split("\n");
      const name =
        lines
          .find((l) => l.startsWith("event:"))
          ?.slice(6)
          .trim() || "message";
      const data = lines
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trimStart())
        .join("\n");
      if (data) onEvent(name, JSON.parse(data));
    }
    if (final && buffer.trim())
      throw new Error("Поток ответа оборвался. Обновите историю.");
  }
  try {
    while (true) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      drain(chunk.done);
      if (chunk.done) break;
    }
  } finally {
    reader.releaseLock();
  }
}
export async function sendTurn(
  chat: string,
  content: string,
  key: string,
  signal: AbortSignal,
  onEvent: (name: string, data: any) => void,
) {
  const token = await accessToken();
  const response = await fetch(
    `${environment.apiBaseUrl}/chats/${chat}/messages`,
    {
      method: "POST",
      signal,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "Idempotency-Key": key,
      },
      body: JSON.stringify({ content }),
    },
  );
  if (!response.ok) {
    if (response.status === 401) endSession();
    const data = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      data.error?.code || "request_failed",
      "Не удалось отправить сообщение. Проверяем сохранённую историю.",
    );
  }
  if (!response.body) throw new Error("Поток ответа недоступен.");
  await readEvents(response.body, onEvent);
}
export function mergeMessage(messages: Message[], message: Message) {
  const index = messages.findIndex((m) => m.id === message.id);
  if (index >= 0) messages[index] = message;
  else messages.push(message);
  messages.sort((a, b) => a.sequence_no - b.sequence_no);
}
