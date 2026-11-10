import { environment } from "../config/environment";
import { accessToken, endSession } from "../auth/session";
import type { ApiErrorResponse } from "./contracts";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: ApiErrorResponse["detail"],
  ) {
    super(message);
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await accessToken();
  let response: Response;
  try {
    response = await fetch(`${environment.apiBaseUrl}${path}`, {
      ...options,
      headers: {
        ...options.headers,
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    throw new ApiError(
      0,
      "network_error",
      "Сервер недоступен. Попробуйте ещё раз.",
    );
  }
  if (!response.ok) {
    if (response.status === 401) endSession();
    const body: ApiErrorResponse = await response.json().catch(() => ({}));
    const messages: Record<number, string> = {
      401: "Сессия завершена. Войдите снова.",
      403: "Доступ к аккаунту ограничен.",
      422: "Проверьте заполненные поля.",
      503: "Сервис временно недоступен. Попробуйте ещё раз.",
    };
    throw new ApiError(
      response.status,
      body.error?.code || "request_failed",
      messages[response.status] ||
        "Не удалось выполнить запрос. Попробуйте ещё раз.",
      body.detail,
    );
  }
  return response.json() as Promise<T>;
}
