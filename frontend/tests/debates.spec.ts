import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
const debate = {
  id: "d1",
  topic_title: "Нужно ли отменить школьные оценки?",
  user_position: "Описательная обратная связь полезнее оценок",
  opponent_position: "Оценки помогают отслеживать прогресс",
  status: "active",
  created_at: "2026-11-09T12:00:00Z",
  chats: [
    {
      id: "c1",
      debate_id: "d1",
      side: "defense",
      title: "Как измерять прогресс без оценок?",
      description: "",
      seed_claim: "",
      opponent_persona_id: "p1",
      difficulty: 1,
      status: "active",
    },
  ],
};
const history = [
  {
    id: "m1",
    chat_id: "c1",
    sequence_no: 1,
    role: "assistant",
    content:
      "**Оценки** дают ученику понятный ориентир. Как вы предлагаете отслеживать прогресс без единой шкалы?",
    generation_status: "completed",
    client_request_id: null,
  },
];
test("advanced debate creation, streaming and responsive workspace", async ({
  page,
}) => {
  test.setTimeout(60000);
  mkdirSync(".impeccable/review", { recursive: true });
  await page.route("**/src/auth/session.ts*", (route) =>
    route.fulfill({
      contentType: "application/javascript",
      body: `import {ref} from '/node_modules/.vite/deps/vue.js'; const authenticated=ref(true); export const initializeSession=async()=>{}; export const accessToken=async()=> 'test'; export const endSession=()=>{}; export const useSession=()=>({authenticated,logout:async()=>{}});`,
    }),
  );
  let rejectTurn = true;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/me"))
      return route.fulfill({
        json: {
          id: "u",
          display_name: "Тест",
          level: "beginner",
          interests: [],
          goals: [],
          preferred_difficulty: 1,
          onboarding_completed: true,
        },
      });
    if (path.endsWith("/categories"))
      return route.fulfill({ json: [{ id: "cat", name: "Образование" }] });
    if (path.endsWith("/opponents"))
      return route.fulfill({
        json: [
          {
            id: "p1",
            name: "Сократ",
            description: "Проверяет аргументы уточняющими вопросами.",
            available_difficulties: [1, 2, 3],
          },
        ],
      });
    if (path.endsWith("/topics"))
      return route.fulfill({
        json: [
          {
            id: "t1",
            title: debate.topic_title,
            description: "Обсудите роль оценивания в обучении.",
            default_positions: [debate.user_position],
          },
        ],
      });
    if (path.endsWith("/advanced")) {
      expect(route.request().postDataJSON()).toMatchObject({
        topic_id: "t1",
        user_position: debate.user_position,
        difficulty: 1,
      });
      return route.fulfill({ json: debate });
    }
    if (path.endsWith("/messages") && route.request().method() === "POST") {
      expect(route.request().headers()["idempotency-key"]).toBeTruthy();
      if (rejectTurn) {
        rejectTurn = false;
        return route.fulfill({
          status: 422,
          json: { error: { code: "invalid_argument" } },
        });
      }
      const user = {
        ...history[0]!,
        id: "m2",
        sequence_no: 2,
        role: "user",
        content: route.request().postDataJSON().content,
      };
      const response = {
        ...history[0]!,
        id: "m3",
        sequence_no: 3,
        content: "",
        generation_status: "generating",
      };
      const finished = {
        ...response,
        content: "Какие критерии обратной связи позволят сравнить результаты?",
        generation_status: "completed",
      };
      history.push(user, finished);
      return route.fulfill({
        contentType: "text/event-stream",
        body: `event: message_started\ndata: ${JSON.stringify({ user_message: user, response })}\n\nevent: delta\ndata: ${JSON.stringify({ content: finished.content })}\n\nevent: message_completed\ndata: ${JSON.stringify(finished)}\n\n`,
      });
    }
    if (
      path.endsWith("/debates/d1/chats") &&
      route.request().method() === "POST"
    ) {
      expect(route.request().postDataJSON().side).toBe("attack");
      const chat = {
        ...debate.chats[0]!,
        id: "c2",
        side: "attack",
        title: "Новый аргумент",
        status: "new",
      };
      debate.chats.push(chat);
      return route.fulfill({ json: chat });
    }
    if (path.endsWith("/chats/c2/messages"))
      return route.fulfill({
        json: Array.from({ length: 30 }, (_, i) => ({
          ...history[0],
          id: `long${i}`,
          chat_id: "c2",
          sequence_no: i + 1,
          content:
            `Аргумент ${i + 1}. **Проверка** длинной истории. ` +
            "Обоснование. ".repeat(25),
        })),
      });
    if (path.endsWith("/chats/c2")) {
      await new Promise((resolve) => setTimeout(resolve, 180));
      return route.fulfill({ json: debate.chats.find((c) => c.id === "c2") });
    }
    if (path.endsWith("/messages")) return route.fulfill({ json: history });
    if (path.endsWith("/chats/c1"))
      return route.fulfill({ json: debate.chats[0] });
    if (path.endsWith("/debates/d1")) return route.fulfill({ json: debate });
    if (path.endsWith("/debates")) return route.fulfill({ json: [debate] });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/debates");
  await page.getByRole("link", { name: "Новые дебаты" }).click();
  await page.getByRole("button", { name: "Продолжить", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Ваша позиция", exact: true }),
  ).toHaveCount(0);
  await page.screenshot({
    path: ".impeccable/review/wizard-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 1000 });
  await page.screenshot({
    path: ".impeccable/review/wizard-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page
    .getByRole("button", {
      name: new RegExp(debate.topic_title.replace("?", "\\?")),
    })
    .click();
  await page.getByRole("button", { name: "Продолжить", exact: true }).click();
  await page
    .getByRole("button", { name: debate.user_position, exact: true })
    .click();
  for (let i = 0; i < 3; i++)
    await page.getByRole("button", { name: "Продолжить", exact: true }).click();
  await page
    .getByRole("button", { name: "Начать дебаты", exact: true })
    .click();
  await page
    .getByRole("link", { name: debate.chats[0]!.title, exact: true })
    .click();
  await expect(page.locator(".message-rich strong")).toHaveText("Оценки");
  await page.getByRole("button", { name: /^Ваш аргумент/ }).click();
  await page
    .getByLabel("Ваш аргумент", { exact: true })
    .fill(
      "Прогресс можно оценивать по заранее известным критериям и примерам работ.",
    );
  await page.getByRole("button", { name: "Отправить", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await page
    .getByLabel("Ваш аргумент")
    .fill(
      "Предлагаю оценивать прогресс по прозрачным критериям и примерам работ.",
    );
  await page.getByRole("button", { name: "Отправить", exact: true }).click();
  await expect(
    page.getByText(
      "Какие критерии обратной связи позволят сравнить результаты?",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /^Ваш аргумент/ }),
  ).toHaveAttribute("aria-expanded", "false");
  await expect(
    page.getByRole("button", { name: "Обновить историю" }),
  ).toHaveCount(0);
  await expect(page.getByRole("link", { name: "К моим дебатам" })).toHaveCount(
    0,
  );
  await page
    .getByRole("button", { name: "Позиции сторон", exact: true })
    .click();
  await expect(
    page.getByText(debate.opponent_position, { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Позиции сторон", exact: true })
    .click();
  await page.getByRole("button", { name: "Добавить подтему защиты" }).click();
  await expect(page.getByLabel("Тезис")).toBeVisible();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "Добавить подтему защиты" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Добавить подтему атаки" }).click();
  await expect(
    page.getByRole("dialog", { name: "Новая подтема атаки" }),
  ).toBeVisible();
  await page.screenshot({
    path: ".impeccable/review/subtopic-modal.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Создать чат", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Новый аргумент", exact: true }),
  ).toBeVisible();
  const size = await page.locator(".conversation").boundingBox();
  const reading = await page.locator(".message-list").boundingBox();
  expect(reading!.height / size!.height).toBeGreaterThan(0.65);
  expect(
    await page
      .locator(".message-list")
      .evaluate((el) => el.scrollHeight > el.clientHeight),
  ).toBe(true);
  const scroll = await page.evaluate(() => window.scrollY);
  await page
    .getByRole("link", { name: debate.chats[0]!.title, exact: true })
    .click();
  await expect(page.locator(".message-list article")).toHaveCount(3);
  expect((await page.locator(".conversation").boundingBox())?.height).toBe(
    size?.height,
  );
  expect(await page.evaluate(() => window.scrollY)).toBe(scroll);
  await page.setViewportSize({ width: 1366, height: 768 });
  expect(
    await page.locator(".message-list").evaluate((el) => el.clientHeight),
  ).toBeGreaterThan(400);
  await page.screenshot({
    path: ".impeccable/review/desktop-768.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: /^Ваш аргумент/ }).click();
  await expect(page.getByLabel("Ваш аргумент", { exact: true })).toBeFocused();
  await page
    .getByLabel("Ваш аргумент", { exact: true })
    .fill("Сохранённый черновик");
  await page.screenshot({
    path: ".impeccable/review/composer-open.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: /^Ваш аргумент/ }).click();
  await page.getByRole("button", { name: /^Ваш аргумент/ }).click();
  await expect(page.getByLabel("Ваш аргумент", { exact: true })).toHaveValue(
    "Сохранённый черновик",
  );
  await page.getByRole("button", { name: /^Ваш аргумент/ }).click();
  for (const [name, width] of [
    ["desktop", 1440],
    ["mobile", 390],
  ] as const) {
    await page.setViewportSize({ width, height: 1000 });
    if (width === 390) {
      const plus = await page
        .getByRole("button", { name: "Добавить подтему атаки" })
        .boundingBox();
      expect(plus!.x + plus!.width).toBeLessThan(390);
    }
    await page.evaluate(() => {
      window.scrollTo(0, 0);
      const log = document.querySelector(".message-list");
      if (log) log.scrollTop = log.scrollHeight;
    });
    await page.screenshot({
      path: `.impeccable/review/${name}.png`,
      fullPage: true,
      animations: "disabled",
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.getByRole("link", { name: "Профиль", exact: true }).click();
  await expect(page.getByRole("button", { name: /Интересы/ })).toBeVisible();
  await page.screenshot({
    path: ".impeccable/review/profile-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: ".impeccable/review/profile-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.goto("/debates/d1/chats/c1");
  await page.reload();
  await expect(
    page.getByText(
      "Какие критерии обратной связи позволят сравнить результаты?",
    ),
  ).toBeVisible();
});
