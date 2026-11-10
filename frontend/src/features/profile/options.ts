import type { Difficulty, ExperienceLevel } from "../../models/profile";
export const levels: { value: ExperienceLevel; label: string }[] = [
  { value: "beginner", label: "Начальный" },
  { value: "intermediate", label: "Средний" },
  { value: "advanced", label: "Продвинутый" },
];
export const goalOptions = [
  "Строить аргументы",
  "Находить логические ошибки",
  "Отвечать на возражения",
  "Выступать публично",
];
export const difficulties: { value: Difficulty; label: string }[] = [
  { value: null, label: "Авто" },
  { value: 1, label: "Лёгкая" },
  { value: 2, label: "Средняя" },
  { value: 3, label: "Высокая" },
];
