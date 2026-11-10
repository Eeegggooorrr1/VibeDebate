export type ExperienceLevel = "beginner" | "intermediate" | "advanced";
export type Difficulty = 1 | 2 | 3 | null;
export interface Profile {
  id: string;
  displayName: string;
  level: ExperienceLevel | null;
  interests: string[];
  goals: string[];
  preferredDifficulty: Difficulty;
  onboardingCompleted: boolean;
}
export interface ProfileDraft {
  displayName: string;
  level: ExperienceLevel | "";
  interests: string[];
  goals: string[];
  preferredDifficulty: Difficulty;
}
export interface Category {
  id: string;
  parentId: string | null;
  name: string;
  slug: string;
}
export type ProfileField = keyof ProfileDraft;
export type ProfileErrors = Partial<Record<ProfileField, string>>;
