import type { Difficulty, ExperienceLevel } from "../models/profile";

export interface UserResponse {
  id: string;
  display_name: string | null;
  status: "active" | "banned" | "deleted";
  level: ExperienceLevel | null;
  goals: string[];
  preferred_difficulty: Difficulty;
  onboarding_completed: boolean;
  interests: string[];
  roles: string[];
}
export interface ProfileUpdateRequest {
  display_name: string;
  level: ExperienceLevel;
  interests: string[];
  goals: string[];
  preferred_difficulty: Difficulty;
}
export interface CategoryResponse {
  id: string;
  parent_id: string | null;
  name: string;
  slug: string;
  description: string;
}
export interface ApiErrorResponse {
  error?: { code: string; message: string; extra?: unknown };
  detail?: { loc: (string | number)[]; msg: string; type: string }[];
}
