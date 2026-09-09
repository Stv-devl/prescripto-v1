/**
 * Regression test for the form→success transition: this component swaps
 * from rendering its own dialog markup to rendering `<SuccessModal>` — a
 * distinct mount, with its own `useModalDialog` call — while staying
 * mounted itself. `isOpen` must therefore track the form view specifically,
 * not "is this component mounted", or the first dialog's Tab-trap listener
 * and scroll-lock acquisition outlive the view they belong to.
 *
 * `@/lib/refCount` is mocked (keeping its real counting behaviour via
 * `importOriginal`) purely to observe call order — `acquire`/`release`
 * are this hook's only documented depth-counted DOM effect, and asserting
 * their order is the only way to prove the old dialog's cleanup ran as
 * part of the same transition instead of leaking until final close.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChangePasswordModal } from "./ChangePasswordModal";

const mutateAsync = vi.fn().mockResolvedValue(undefined);

vi.mock("../hooks/hooks", () => ({
  useChangePassword: () => ({ mutateAsync, isPending: false }),
}));

const refCountCalls: Array<{ op: "acquire" | "release"; target: unknown }> =
  [];

vi.mock("@/lib/refCount", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/refCount")>();
  return {
    acquire: (target: object, apply: () => void) => {
      refCountCalls.push({ op: "acquire", target });
      actual.acquire(target, apply);
    },
    release: (target: object, revert: () => void) => {
      refCountCalls.push({ op: "release", target });
      actual.release(target, revert);
    },
  };
});

afterEach(() => {
  refCountCalls.length = 0;
  document.body.classList.remove("overflow-hidden");
});

async function submitValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(
    screen.getByLabelText("Mot de passe actuel"),
    "OldPassw0rd!",
  );
  await user.type(
    screen.getByLabelText("Nouveau mot de passe"),
    "NewPassw0rd!",
  );
  await user.type(
    screen.getByLabelText("Confirmer le nouveau mot de passe"),
    "NewPassw0rd!",
  );
  await user.click(screen.getByRole("button", { name: "Modifier" }));
}

describe("ChangePasswordModal — form→success dialog lifecycle", () => {
  it("releases the form dialog's scroll lock before the success dialog acquires its own", async () => {
    const user = userEvent.setup();
    render(<ChangePasswordModal onClose={vi.fn()} />);

    await submitValidForm(user);

    await waitFor(() => {
      expect(
        screen.getByText("Votre mot de passe a été modifié avec succès."),
      ).toBeInTheDocument();
    });

    const bodyOps = refCountCalls
      .filter((call) => call.target === document.body)
      .map((call) => call.op);

    expect(bodyOps).toEqual(["acquire", "release", "acquire"]);
  });

  it("removes the form dialog's Tab-trap listener once the success dialog is shown", async () => {
    const removeSpy = vi.spyOn(document, "removeEventListener");
    const addSpy = vi.spyOn(document, "addEventListener");
    const user = userEvent.setup();
    render(<ChangePasswordModal onClose={vi.fn()} />);

    const keydownAddsAtMount = addSpy.mock.calls.filter(
      ([type]) => type === "keydown",
    ).length;
    expect(keydownAddsAtMount).toBe(2);

    await submitValidForm(user);

    await waitFor(() => {
      expect(
        screen.getByText("Votre mot de passe a été modifié avec succès."),
      ).toBeInTheDocument();
    });

    const keydownRemoves = removeSpy.mock.calls.filter(
      ([type]) => type === "keydown",
    ).length;
    const keydownAdds = addSpy.mock.calls.filter(
      ([type]) => type === "keydown",
    ).length;

    expect(keydownRemoves).toBe(1);
    expect(keydownAdds).toBe(4);

    removeSpy.mockRestore();
    addSpy.mockRestore();
  });
});
