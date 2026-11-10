import type {
  Category,
  ProfileDraft,
  ProfileErrors,
} from "../../models/profile";

export function validateProfile(
  draft: ProfileDraft,
  categories: Category[],
): ProfileErrors {
  const errors: ProfileErrors = {};
  const name = draft.displayName.trim();
  if (!name || name.length > 255)
    errors.displayName = "Введите имя от 1 до 255 символов.";
  if (!["beginner", "intermediate", "advanced"].includes(draft.level))
    errors.level = "Выберите уровень.";
  if (!draft.interests.length)
    errors.interests = "Выберите хотя бы одну область.";
  else if (
    draft.interests.length > 20 ||
    new Set(draft.interests).size !== draft.interests.length ||
    draft.interests.some(
      (id) => !categories.some((category) => category.id === id),
    )
  )
    errors.interests = "Выберите до 20 доступных областей.";
  const goals = draft.goals.map((goal) => goal.trim());
  if (!goals.length) errors.goals = "Выберите хотя бы одну цель.";
  else if (
    goals.length > 10 ||
    goals.some((goal) => !goal || goal.length > 100) ||
    new Set(goals).size !== goals.length
  )
    errors.goals = "Выберите до 10 разных целей.";
  if (![null, 1, 2, 3].includes(draft.preferredDifficulty))
    errors.preferredDifficulty = "Выберите сложность.";
  return errors;
}
