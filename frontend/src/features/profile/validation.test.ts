import { describe, expect, it } from "vitest";
import { validateProfile } from "./validation";
import { profilePayload } from "../../api/profile";
import type { ProfileDraft } from "../../models/profile";

const categories = [
  { id: "category-a", parentId: null, name: "Философия", slug: "philosophy" },
];
const valid = (): ProfileDraft => ({
  displayName: "  Егор  ",
  level: "beginner",
  interests: ["category-a"],
  goals: ["Логика"],
  preferredDifficulty: null,
});
describe("profile contract", () => {
  it("keeps automatic difficulty as null and trims the display name for the API", () => {
    expect(validateProfile(valid(), categories)).toEqual({});
    expect(profilePayload(valid())).toEqual({
      display_name: "Егор",
      level: "beginner",
      interests: ["category-a"],
      goals: ["Логика"],
      preferred_difficulty: null,
    });
  });
  it("rejects unknown or inactive category ids and duplicates", () => {
    expect(
      validateProfile({ ...valid(), interests: ["removed"] }, categories)
        .interests,
    ).toBeTruthy();
    expect(
      validateProfile(
        { ...valid(), interests: ["category-a", "category-a"] },
        categories,
      ).interests,
    ).toBeTruthy();
  });
  it("rejects whitespace-only names and goals that become duplicates after trimming", () => {
    expect(
      validateProfile(
        { ...valid(), displayName: "   ", goals: ["Логика", " Логика "] },
        categories,
      ),
    ).toHaveProperty("displayName");
    expect(
      validateProfile({ ...valid(), goals: ["Логика", " Логика "] }, categories)
        .goals,
    ).toBeTruthy();
  });
  it("requires all three onboarding selections and respects backend limits", () => {
    expect(
      Object.keys(
        validateProfile(
          { ...valid(), level: "", interests: [], goals: [] },
          categories,
        ),
      ),
    ).toEqual(["level", "interests", "goals"]);
    expect(
      validateProfile({ ...valid(), goals: ["x".repeat(101)] }, categories)
        .goals,
    ).toBeTruthy();
  });
});
