import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ServiceFailure } from "@/lib/result";
import { ErrorMessage } from "./ErrorMessage";

describe("ErrorMessage — comportement principal", () => {
  it("ne rend rien quand error est null", () => {
    const { container } = render(<ErrorMessage error={null} />);

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("rend la copie française d'un code connu", () => {
    render(
      <ErrorMessage
        error={new ServiceFailure({ code: "forbidden", message: "forbidden" })}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Accès refusé");
  });

  it("retombe sur le texte générique pour un code inconnu", () => {
    render(
      <ErrorMessage
        error={
          new ServiceFailure({
            code: "totally_unmapped_code",
            message: "unmapped",
          })
        }
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Une erreur est survenue",
    );
  });

  it("porte role=alert, avec ou sans inline", () => {
    const error = new ServiceFailure({ code: "forbidden", message: "x" });
    const { rerender } = render(<ErrorMessage error={error} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();

    rerender(<ErrorMessage error={error} inline />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

describe("ErrorMessage — règles métier", () => {
  it("la classe par défaut référence le token --destructive, sans couleur codée en dur", () => {
    render(
      <ErrorMessage
        error={new ServiceFailure({ code: "forbidden", message: "x" })}
      />,
    );

    const className = screen.getByRole("alert").className;
    expect(className).toContain("hsl(var(--destructive))");
    expect(className).not.toMatch(/red-(50|400|500|700)/);
  });

  it("inline rend une classe compacte, distincte du bloc", () => {
    const error = new ServiceFailure({ code: "forbidden", message: "x" });
    const { rerender } = render(<ErrorMessage error={error} />);
    const blockClassName = screen.getByRole("alert").className;

    rerender(<ErrorMessage error={error} inline />);
    const inlineClassName = screen.getByRole("alert").className;

    expect(inlineClassName).not.toBe(blockClassName);
    expect(inlineClassName).not.toContain("border");
    expect(inlineClassName).not.toContain("p-4");
  });

  it("un className explicite prend le pas sur inline", () => {
    render(
      <ErrorMessage
        error={new ServiceFailure({ code: "forbidden", message: "x" })}
        inline
        className="custom-class"
      />,
    );

    expect(screen.getByRole("alert")).toHaveClass("custom-class");
    expect(screen.getByRole("alert").className).toBe("custom-class");
  });
});

describe("ErrorMessage — réessai", () => {
  it("ne rend aucun bouton quand aucun réessai n'est fourni", () => {
    const error = new ServiceFailure({ code: "network_error", message: "x" });

    render(<ErrorMessage error={error} />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("rend un bouton de réessai et appelle le rappel au clic", async () => {
    const error = new ServiceFailure({ code: "network_error", message: "x" });
    const onRetry = vi.fn();

    render(<ErrorMessage error={error} onRetry={onRetry} />);
    await userEvent.click(screen.getByRole("button"));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("garde le message d'erreur à côté du bouton", () => {
    // The button is added to the message, never in place of it: a surface that
    // showed only the retry control would no longer say what failed.
    const error = new ServiceFailure({ code: "network_error", message: "x" });

    render(<ErrorMessage error={error} onRetry={() => {}} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Erreur de connexion");
  });
});

describe("ErrorMessage — cas limites", () => {
  it("inline={false} explicite rend la même classe que l'absence de la prop", () => {
    const error = new ServiceFailure({ code: "forbidden", message: "x" });
    const { rerender } = render(<ErrorMessage error={error} />);
    const defaultClassName = screen.getByRole("alert").className;

    rerender(<ErrorMessage error={error} inline={false} />);

    expect(screen.getByRole("alert").className).toBe(defaultClassName);
  });
});
