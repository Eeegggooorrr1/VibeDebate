import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import type { UserResponse, ProfileUpdateRequest } from "../src/api/contracts";

for (const realApi of [false, true])
  test(`registration and questionnaire (${realApi ? "real API" : "controlled API"})`, async ({
    page,
    request,
  }) => {
    test.setTimeout(90_000);
    const email = `e2e-${Date.now()}@example.test`;
    const password = `Test-${crypto.randomUUID()}!`;
    const categoryId = "10000000-0000-0000-0000-000000000001";
    let user: UserResponse = {
      id: crypto.randomUUID(),
      display_name: "Тест",
      status: "active",
      level: null,
      interests: [],
      goals: [],
      preferred_difficulty: null,
      onboarding_completed: false,
      roles: ["user"],
    };
    let failSave = true;
    let lastPayload: ProfileUpdateRequest | undefined;
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/v1/**", async (route) => {
      const req = route.request();
      expect(req.headers().authorization).toMatch(/^Bearer .+/);
      if (realApi && req.method() !== "PATCH") return route.continue();
      if (req.url().endsWith("/topics/categories"))
        return route.fulfill({
          json: [
            {
              id: categoryId,
              parent_id: null,
              name: "Философия",
              slug: "philosophy",
              description: "",
            },
          ],
        });
      if (req.method() === "PATCH") {
        if (failSave) {
          failSave = false;
          return route.fulfill({
            status: 503,
            json: { error: { code: "unavailable", message: "Unavailable" } },
          });
        }
        lastPayload = req.postDataJSON() as ProfileUpdateRequest;
        if (realApi) return route.continue();
        user = { ...user, ...lastPayload, onboarding_completed: true };
      }
      return route.fulfill({ json: user });
    });
    try {
      await expect
        .poll(
          async () => {
            try {
              return (
                await request.get(
                  "http://localhost:8180/realms/vibedebate/.well-known/openid-configuration",
                )
              ).status();
            } catch {
              return 0;
            }
          },
          { timeout: 45_000 },
        )
        .toBe(200);
      await page.goto("/");
      await page
        .getByRole("button", { name: "Создать аккаунт", exact: true })
        .click();
      await expect(page.locator("body")).toHaveClass(/custom-auth/);
      await expect(
        page.getByRole("heading", { name: "Создать аккаунт" }),
      ).toBeVisible();
      await page.getByLabel("Электронная почта", { exact: true }).fill(email);
      await page.getByLabel("Пароль", { exact: true }).fill(password);
      await page.getByLabel("Повторите пароль", { exact: true }).fill(password);
      await page.getByLabel("Имя", { exact: true }).fill("Тест");
      await page.getByLabel("Фамилия", { exact: true }).fill("Пользователь");
      await page.screenshot({
        path: ".impeccable/review/registration-desktop.png",
        fullPage: true,
      });
      await page
        .getByRole("button", { name: "Создать аккаунт", exact: true })
        .click();
      await expect(page).toHaveURL(/\/onboarding$/);
      await page.getByRole("button", { name: "Продолжить" }).click();
      await expect(
        page.getByText("Выберите уровень.", { exact: true }),
      ).toBeVisible();
      await page.getByLabel("Имя", { exact: true }).fill("Александр");
      await page.getByRole("radio", { name: "Средний", exact: true }).check();
      await page.getByRole("checkbox", { name: "Философия" }).check();
      await page.getByRole("checkbox", { name: "Строить аргументы" }).check();
      await page.getByRole("button", { name: /Сложность/ }).click();
      await page.getByRole("radio", { name: "Высокая" }).check();
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.screenshot({
        path: ".impeccable/review/onboarding-desktop.png",
        fullPage: true,
      });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all(
          document
            .getAnimations()
            .map((animation) => animation.finished.catch(() => undefined)),
        );
      });
      await page.screenshot({
        path: ".impeccable/review/onboarding-mobile.png",
        fullPage: true,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page.getByRole("button", { name: "Продолжить" }).click();
      await expect(page.getByRole("alert")).toHaveText(
        "Сервис временно недоступен. Попробуйте ещё раз.",
      );
      await expect(page.getByLabel("Имя", { exact: true })).toHaveValue(
        "Александр",
      );
      await page.getByRole("button", { name: "Продолжить" }).click();
      await expect(page).toHaveURL(/\/profile$/);
      expect(lastPayload).toEqual({
        display_name: "Александр",
        level: "intermediate",
        interests: [categoryId],
        goals: ["Строить аргументы"],
        preferred_difficulty: 3,
      });
      await page.getByRole("button", { name: "Редактировать" }).click();
      await expect(page.getByLabel("Имя", { exact: true })).toHaveValue(
        "Александр",
      );
      await page.getByLabel("Имя", { exact: true }).fill("Александр П.");
      await page
        .getByRole("button", { name: "Сохранить", exact: true })
        .click();
      await expect(
        page.getByText("Александр П.", { exact: true }),
      ).toBeVisible();
      await page.reload();
      await expect(page).toHaveURL(/\/profile$/);
      await expect(
        page.getByText("Александр П.", { exact: true }),
      ).toBeVisible();
      expect(
        await page.evaluate(() =>
          [...Object.keys(localStorage), ...Object.keys(sessionStorage)].some(
            (key) => /token/i.test(key),
          ),
        ),
      ).toBe(false);
      await page.getByRole("button", { name: "Выйти", exact: true }).click();
      await expect(
        page.getByRole("button", { name: "Создать аккаунт", exact: true }),
      ).toBeVisible();
      await page.getByRole("button", { name: "Войти", exact: true }).click();
      await expect(
        page.getByRole("heading", { name: "Вход", exact: true }),
      ).toBeVisible();
      await expect(page.locator("body")).toHaveClass(/custom-auth/);
      await page.getByLabel("Электронная почта", { exact: true }).fill(email);
      await page.getByLabel("Пароль", { exact: true }).fill(password);
      await page.getByRole("button", { name: "Войти", exact: true }).click();
      await expect(page).toHaveURL(/\/profile$/);
      expect(errors).toEqual([]);
    } finally {
      const token = await request.post(
        "http://localhost:8180/realms/master/protocol/openid-connect/token",
        {
          form: {
            client_id: "admin-cli",
            grant_type: "password",
            username: process.env.E2E_ADMIN_USERNAME || "",
            password: process.env.E2E_ADMIN_PASSWORD || "",
          },
        },
      );
      expect(token.ok(), "test account cleanup: admin login").toBe(true);
      const { access_token } = await token.json();
      const headers = { Authorization: `Bearer ${access_token}` };
      const found = await request.get(
        `http://localhost:8180/admin/realms/vibedebate/users?email=${encodeURIComponent(email)}&exact=true`,
        { headers },
      );
      for (const account of await found.json()) {
        if (realApi)
          execFileSync(
            "docker",
            [
              "compose",
              "-f",
              "compose.yml",
              "-f",
              "compose.theme.yml",
              "--env-file",
              "../.env",
              "exec",
              "-T",
              "backend",
              "python",
              "-",
              account.id,
            ],
            {
              input: readFileSync(
                new URL("./cleanup-profile.py", import.meta.url),
              ),
              stdio: ["pipe", "pipe", "pipe"],
            },
          );
        const result = await request.delete(
          `http://localhost:8180/admin/realms/vibedebate/users/${account.id}`,
          { headers },
        );
        expect(result.ok(), "test account cleanup: delete").toBe(true);
      }
    }
  });
