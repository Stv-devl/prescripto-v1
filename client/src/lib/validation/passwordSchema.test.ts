import { describe, expect, it } from "vitest";
import { passwordRules } from "./passwordSchema";

function messagesFor(input: string): string[] {
  const result = passwordRules.safeParse(input);
  return result.success ? [] : result.error.issues.map((issue) => issue.message);
}

describe("passwordRules", () => {
  it("accepts a password that satisfies the five rules", () => {
    expect(passwordRules.safeParse("Abcdefg1!").success).toBe(true);
  });

  it("rejects fewer than 8 characters", () => {
    expect(messagesFor("Ab1!")).toEqual(["8 caractères minimum"]);
  });

  it("rejects more than 72 bytes", () => {
    expect(messagesFor(`A1!${"a".repeat(70)}`)).toEqual(["72 octets maximum"]);
  });

  it("rejects an accented password well under 72 characters", () => {
    // 43 characters, 83 UTF-8 bytes. The suffix is uppercase-digit-symbol on
    // purpose: an accented capital is outside [A-Z], so a lowercase suffix
    // would trip the character rules instead and prove nothing about bytes.
    expect(messagesFor(`${"É".repeat(40)}A1!`)).toEqual(["72 octets maximum"]);
  });

  it("rejects a password without an uppercase letter", () => {
    expect(messagesFor("abcdefg1!")).toEqual([
      "Doit contenir au moins une majuscule",
    ]);
  });

  it("rejects a password without a digit", () => {
    expect(messagesFor("Abcdefgh!")).toEqual([
      "Doit contenir au moins un chiffre",
    ]);
  });

  it("rejects a password without a special character", () => {
    expect(messagesFor("Abcdefg1")).toEqual([
      "Doit contenir au moins un caractère spécial",
    ]);
  });

  it("accepts exactly 8 characters", () => {
    expect(passwordRules.safeParse("Abcdef1!").success).toBe(true);
  });

  it("accepts exactly 72 bytes", () => {
    // The bound is inclusive: 72 is bcrypt's own limit, not one past it.
    expect(passwordRules.safeParse(`A1!${"a".repeat(69)}`).success).toBe(true);
  });

  it("reports the four broken rules for an empty string", () => {
    expect(messagesFor("")).toEqual([
      "8 caractères minimum",
      "Doit contenir au moins une majuscule",
      "Doit contenir au moins un chiffre",
      "Doit contenir au moins un caractère spécial",
    ]);
  });
});
