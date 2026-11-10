import { request } from "./http";
import type {
  CategoryResponse,
  ProfileUpdateRequest,
  UserResponse,
} from "./contracts";
import type { Category, Profile, ProfileDraft } from "../models/profile";

export function mapProfile(dto: UserResponse): Profile {
  return {
    id: dto.id,
    displayName: dto.display_name ?? "",
    level: dto.level,
    interests: dto.interests,
    goals: dto.goals,
    preferredDifficulty: dto.preferred_difficulty,
    onboardingCompleted: dto.onboarding_completed,
  };
}
export function profilePayload(draft: ProfileDraft): ProfileUpdateRequest {
  if (!draft.level) throw new Error("Выберите уровень.");
  return {
    display_name: draft.displayName.trim(),
    level: draft.level,
    interests: [...draft.interests],
    goals: draft.goals.map((goal) => goal.trim()),
    preferred_difficulty: draft.preferredDifficulty,
  };
}
export const getProfile = async () =>
  mapProfile(await request<UserResponse>("/me"));
export const updateProfile = async (draft: ProfileDraft) =>
  mapProfile(
    await request<UserResponse>("/me/profile", {
      method: "PATCH",
      body: JSON.stringify(profilePayload(draft)),
    }),
  );
export async function getCategories(): Promise<Category[]> {
  return (await request<CategoryResponse[]>("/topics/categories")).map(
    (dto) => ({
      id: dto.id,
      parentId: dto.parent_id,
      name: dto.name,
      slug: dto.slug,
    }),
  );
}
