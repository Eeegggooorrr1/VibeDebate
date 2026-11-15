import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";

let exerciseCalls = 0;
test("suggestion acceptance and analysis states on desktop and mobile", async ({
  page,
}) => {
  test.setTimeout(90000);
  mkdirSync(".impeccable/review", { recursive: true });
  await page.route("**/src/auth/session.ts*", (route) =>
    route.fulfill({
      contentType: "application/javascript",
      body: `import {ref} from '/node_modules/.vite/deps/vue.js'; const authenticated=ref(true); export const initializeSession=async()=>{}; export const accessToken=async()=> 'test'; export const endSession=()=>{}; export const useSession=()=>({authenticated,logout:async()=>{}});`,
    }),
  );
  const chat = {
    id: "c1",
    debate_id: "d1",
    side: "defense",
    title: "Как измерять прогресс без оценок?",
    description: "",
    seed_claim: "Оценки необходимы",
    opponent_persona_id: "p1",
    difficulty: 1,
    status: "active",
  };
  const chats: any[] = [
    chat,
    ...Array.from({ length: 12 }, (_, i) => ({
      ...chat,
      id: `extra${i}`,
      title: `${chat.title} ${i + 1}`,
    })),
  ];
  const history = [
    {
      id: "m1",
      chat_id: "c1",
      sequence_no: 1,
      role: "assistant",
      content:
        "Я считаю, что оценки дают ученику понятный ориентир. Как вы предлагаете отслеживать прогресс без единой шкалы?",
      generation_status: "completed",
      client_request_id: null,
    },
    {
      id: "m2",
      chat_id: "c1",
      sequence_no: 2,
      role: "user",
      content:
        "Оценки всегда мешают учиться. Все мои друзья считают, что без них было бы лучше.",
      generation_status: "completed",
      client_request_id: "turn",
    },
  ];
  Object.assign(history[1]!, {
    reply_to_message_id: "m1",
    reply_to_content: history[0]!.content,
  });
  let status = "running",
    suggestionCalls = 0,
    createCalls = 0;
  const result = {
    message_id: "m2",
    status: "completed",
    is_substantive: true,
    overall_score: 42.5,
    confidence: 0.8,
    dimensions: [
      {
        key: "evidence_quality",
        score: 1,
        applicable: true,
        explanation:
          "Мнения друзей не показывают эффект оценок для всех учеников.",
      },
    ],
    strengths: ["Позиция сформулирована прямо."],
    conduct_flags: [],
    next_step:
      "Уточните, в каких условиях оценки мешают учиться, и приведите проверяемый пример.",
    issues: [
      {
        type: "overgeneralization",
        severity: "high",
        evidence_quote: "Оценки всегда мешают учиться.",
        explanation:
          "Слово «всегда» распространяет вывод на любые условия, но это не обосновано.",
        improvement:
          "Ограничьте тезис конкретными условиями и рассмотрите исключения.",
        confidence: 0.9,
      },
      {
        type: "weak_evidence",
        severity: "medium",
        evidence_quote: "Все мои друзья считают",
        explanation: "Мнения небольшой группы не доказывают причинную связь.",
        improvement: "Отделите мнение от данных об учебных результатах.",
        confidence: 0.8,
      },
    ],
  };
  const archived: string[] = [];
  let replySubmitted = false;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === "DELETE") {
      archived.push(path);
      return route.fulfill({ json: { archived: true } });
    }
    if (path.endsWith("/debates")) return route.fulfill({ json: [] });

    if (path.endsWith("/exercises/check"))
      return route.fulfill({
        json: {
          achieved: true,
          feedback: "The premise connects the conclusion.",
          next_question: "",
        },
      });
    if (path.endsWith("/exercises")) {
      expect(route.request().postDataJSON()).not.toHaveProperty("kind");
      const kind = ["quiz", "order", "premise", "rewrite", "coach"][
        exerciseCalls++ % 5
      ]!;
      return route.fulfill({
        json: {
          kind,
          title: "Practice the argument",
          instruction: "Find the missing premise.",
          items: ["quiz", "order"].includes(kind)
            ? ["First premise", "Second premise", "Conclusion"]
            : [],
          solution: kind === "quiz" ? [1] : kind === "order" ? [0, 1, 2] : [],
          explanation: "The premises support the conclusion.",
          criteria: "Valid reasoning",
        },
      });
    }

    if (path.endsWith("/me"))
      return route.fulfill({
        json: {
          id: "u",
          display_name: "Тест",
          onboarding_completed: true,
          level: "beginner",
          interests: [],
          goals: [],
          preferred_difficulty: 1,
        },
      });
    if (path.endsWith("/categories")) return route.fulfill({ json: [] });
    if (path.endsWith("/opponents"))
      return route.fulfill({
        json: [{ id: "p1", name: "Сократ", available_difficulties: [1, 2, 3] }],
      });
    if (path.endsWith("/analysis/retry")) {
      status = "completed";
      return route.fulfill({ json: result });
    }
    if (path.endsWith("/analysis"))
      return route.fulfill({
        json: {
          ...result,
          status,
          ...(status !== "completed"
            ? { issues: [], overall_score: null }
            : {}),
        },
      });
    if (path.endsWith("/chat-suggestions")) {
      suggestionCalls++;
      expect(createCalls).toBe(0);
      const side = route.request().postDataJSON().side;
      return route.fulfill({
        json: {
          title: `Обратная связь ${suggestionCalls}`,
          description: "Роль понятных критериев в обучении.",
          seed_claim:
            "Я считаю, что понятные критерии необходимы. Чем вы предлагаете их заменить?",
          hint:
            side === "attack"
              ? "Объясните, как описательная обратная связь помогает ученику исправлять ошибки. Приведите пример."
              : null,
        },
      });
    }
    if (
      path.endsWith("/debates/d1/chats") &&
      route.request().method() === "POST"
    ) {
      createCalls++;
      const body = route.request().postDataJSON();
      expect(body.accepted_suggestion.title).toBe("Обратная связь 2");
      const accepted = {
        ...chat,
        ...body.accepted_suggestion,
        id: "c2",
        side: body.side,
        attack_hint: body.accepted_suggestion.hint,
      };
      chats.push(accepted);
      return route.fulfill({ json: accepted });
    }
    if (
      path.endsWith("/chats/c1/messages") &&
      route.request().method() === "POST"
    ) {
      const body = route.request().postDataJSON();
      expect(body.reply_to_message_id).toBe("m1");
      expect(body.content).toBe("Принимаю указанную предпосылку.");
      replySubmitted = true;
      const user = {
        ...history[1]!,
        id: "m3",
        sequence_no: 3,
        content: body.content,
        client_request_id: route.request().headers()["idempotency-key"] || null,
        reply_to_message_id: "m1",
        reply_to_content: history[0]!.content,
      };
      const response = {
        ...history[0]!,
        id: "m4",
        sequence_no: 4,
        content: "Продолжим рассуждение.",
      };
      history.push(user, response);
      const event = (name: string, data: unknown) =>
        `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
      return route.fulfill({
        contentType: "text/event-stream",
        body:
          event("message_started", {
            user_message: user,
            response: {
              ...response,
              generation_status: "generating",
              content: "",
            },
          }) + event("message_completed", response),
      });
    }
    if (path.endsWith("/chats/c1/messages"))
      return route.fulfill({ json: history });
    if (path.endsWith("/chats/c2/messages")) return route.fulfill({ json: [] });
    if (path.endsWith("/chats/c1")) return route.fulfill({ json: chat });
    if (path.endsWith("/chats/c2"))
      return route.fulfill({ json: chats.find((c) => c.id === "c2") });
    if (path.endsWith("/debates/d1"))
      return route.fulfill({
        json: {
          id: "d1",
          topic_title: "Нужно ли отменить школьные оценки?",
          user_position: "Обратная связь полезнее оценок",
          opponent_position: "Оценки помогают отслеживать прогресс",
          status: "active",
          chats,
        },
      });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/debates/d1/chats/c1");
  await expect(
    page.locator(".chat-progress-button .chat-progress--unrated"),
  ).toBeVisible();
  await expect(page.getByText("Анализируем…", { exact: true })).toBeVisible();
  await page.screenshot({
    path: ".impeccable/review/analysis-running.png",
    fullPage: true,
    animations: "disabled",
  });
  const sidebar = page.locator(".chat-sidebar-scroll");
  await sidebar.evaluate((el) => (el.scrollTop = el.scrollHeight));
  await page.screenshot({
    path: ".impeccable/review/sidebar-scrolled.png",
    fullPage: true,
    animations: "disabled",
  });
  await sidebar.evaluate((el) => (el.scrollTop = 0));
  const panel = await page.locator(".analysis-panel").boundingBox();
  const conversation = await page.locator(".conversation").boundingBox();
  expect(panel!.height).toBeLessThan(conversation!.height / 2);
  await page
    .getByRole("button", { name: "Ответить на сообщение оппонента" })
    .first()
    .click();
  await expect(page.locator(".reply-preview")).toBeVisible();
  await expect(page.locator(".reply-preview")).toContainText(
    history[0]!.content,
  );
  await page.screenshot({
    path: ".impeccable/review/reply-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: ".impeccable/review/reply-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page
    .getByRole("button", { name: "Отменить ответ на сообщение" })
    .click();
  await expect(page.locator(".reply-preview")).toHaveCount(0);
  await page.getByRole("button", { name: /Ваш аргумент/ }).click();
  await expect(
    page.getByRole("button", { name: "Перейти к сообщению оппонента" }),
  ).toBeVisible();

  status = "completed";
  await expect(
    page.locator(".analysis-preview").getByText("42.5 / 100", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: ".impeccable/review/analysis-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "Посмотреть анализ этого ответа" })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Разбор ответа" }),
  ).toBeVisible();
  await expect(page.getByText("Как улучшить:").first()).toBeVisible();
  await page.screenshot({
    path: ".impeccable/review/analysis-detail-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await expect(
    page.getByRole("heading", { name: "Необоснованное обобщение" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Недостаточные основания" }),
  ).toBeVisible();
  const criteria = page.getByRole("button", {
    name: "По критериям",
    exact: true,
  });
  await criteria.scrollIntoViewIfNeeded();
  await expect(criteria).toHaveAttribute("aria-expanded", "false");
  await criteria.focus();
  await page.keyboard.press("Enter");
  await expect(criteria).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator(".analysis-dimensions")).toBeVisible();

  await page.screenshot({
    path: ".impeccable/review/analysis-detail-bottom.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.locator(".exercise-entry").first().click();
  const training = page.getByRole("dialog", {
    name: "Тренировка аргументации",
  });
  await expect(training.getByText("Practice the argument")).toBeVisible();
  await training.getByRole("radio").nth(1).check();
  await training.locator('button[type="submit"]').click();
  await expect(training.locator(".exercise-feedback")).toBeVisible();
  for (const kind of ["order", "premise", "rewrite", "coach"]) {
    await training
      .getByRole("button", { name: "Другое упражнение по этой ошибке" })
      .click();
    await expect(training.getByText("Practice the argument")).toBeVisible();
    if (kind !== "order")
      await training
        .locator("textarea")
        .fill("The missing premise explains why the conclusion follows.");
    await training.locator('button[type="submit"]').click();
    await expect(training.locator(".exercise-feedback")).toBeVisible();
  }
  await page.screenshot({
    path: ".impeccable/review/exercise-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: ".impeccable/review/exercise-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.keyboard.press("Escape");
  await expect(training).not.toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Посмотреть анализ этого ответа" }),
  ).toBeFocused();
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.screenshot({
    path: ".impeccable/review/analysis-tablet.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: ".impeccable/review/analysis-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Открыть подробный анализ ответа" })
    .click();
  await page.screenshot({
    path: ".impeccable/review/analysis-detail-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Закрыть окно" }).click();
  await page.getByRole("button", { name: "Добавить подтему атаки" }).click();
  await page
    .getByRole("button", { name: "Предложить тему с помощью ИИ" })
    .focus();
  await expect(page.getByRole("tooltip")).toBeVisible();
  await page
    .getByRole("button", { name: "Предложить тему с помощью ИИ" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Обратная связь 1" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Другой вариант" }).click();
  await expect(
    page.getByRole("heading", { name: "Обратная связь 2" }),
  ).toBeVisible();
  expect(createCalls).toBe(0);
  await page.screenshot({
    path: ".impeccable/review/suggest-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Принять и начать диалог" }).click();
  await expect(page).toHaveURL(/chats\/c2$/);
  await expect(page.getByText("Подсказка ИИ", { exact: true })).toBeVisible();
  await expect(page.locator(".message")).toHaveCount(0);
  expect(createCalls).toBe(1);
  expect(suggestionCalls).toBe(2);
  await page.screenshot({
    path: ".impeccable/review/attack-hint-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  // A failed analysis is retryable without resending the user's argument.
  status = "failed";
  await page.goto("/debates/d1/chats/c1");
  await expect(page.getByText("Разбор не завершён")).toBeVisible();
  await page
    .getByRole("button", { name: "Открыть подробный анализ ответа" })
    .click();
  await page
    .getByRole("button", { name: "Повторить анализ", exact: true })
    .click();
  await expect(page.getByText("Как улучшить:").first()).toBeVisible();
  await page.getByRole("button", { name: "Закрыть окно" }).click();
  Object.assign(chat, {
    progress: 100,
    scored_answers: 2,
    score_total: 40,
    good_streak: 0,
    mastery_source: "opponent_concession",
    mastered_at: "2026-11-11T12:00:00Z",
  });
  status = "completed";
  await page.goto("/debates/d1/chats/c1");
  await expect(
    page.getByText("Отличная работа!", { exact: false }),
  ).toBeVisible();
  await expect(page.locator(".chat-sidebar .chat-progress")).toHaveCount(0);
  await page.getByRole("button", { name: "Открыть прогресс чата" }).click();
  await expect(
    page.getByRole("progressbar", { name: "Прогресс чата" }),
  ).toHaveAttribute("aria-valuenow", "100");
  await expect(
    page.getByRole("heading", { name: "Когда чат считается пройденным" }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Средний балл 20.0", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("Оппонент признал победу", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: ".impeccable/review/progress-detail-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Закрыть окно" }).click();

  await page.screenshot({
    path: ".impeccable/review/progress-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({
    path: ".impeccable/review/progress-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "Ответить на сообщение оппонента" })
    .first()
    .click();
  await page.locator("#argument").fill("Принимаю указанную предпосылку.");
  await page.getByRole("button", { name: "Отправить", exact: true }).click();
  await expect(page.locator("#message-m3 .message-reply")).toContainText(
    history[0]!.content,
  );
  await expect(page.locator(".reply-preview")).toHaveCount(0);
  expect(replySubmitted).toBe(true);
  await expect(
    page.getByRole("button", { name: "Удалить дебаты", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: `Удалить чат: ${chat.title}`, exact: true })
    .click();
  await page.getByRole("button", { name: "Удалить", exact: true }).click();
  await expect(page).toHaveURL(/debates\/d1$/);
  expect(archived).toContain("/api/v1/chats/c1");
});
