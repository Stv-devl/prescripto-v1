import { describe, expect, it } from "vitest";
import type { ProjectSummaryWire } from "../types/types";
import { toProjectSummary } from "./summary.mapper";

/**
 * Payloads the backend can emit but `ProjectSummaryWire` forbids at compile
 * time: one localised cast, so no case needs `any`.
 */
function malformedWire(raw: Record<string, unknown>): ProjectSummaryWire {
  return raw as unknown as ProjectSummaryWire;
}

describe("toProjectSummary", () => {
  it("renders systemeConstructif from the wire's systeme_constructif", () => {
    const wire: ProjectSummaryWire = {
      description: "Groupe scolaire de 12 classes, marché en lots séparés.",
      systeme_constructif: [
        {
          label: "Infrastructure",
          description: "Fondations superficielles sur bon sol à 1,20 m.",
          kpis: ["Semelles filantes 50×20 cm"],
          details: ["Soubassement en agglomérés pleins 20 cm"],
        },
        {
          label: "Superstructure",
          description: "Murs en blocs béton avec doublage intérieur.",
          kpis: ["Murs en agglomérés creux 20 cm"],
          details: ["Doublage 13+100 sur ossature métallique"],
        },
      ],
      contraintes: [],
    };

    expect(toProjectSummary(wire).systemeConstructif).toEqual([
      {
        label: "Infrastructure",
        description: "Fondations superficielles sur bon sol à 1,20 m.",
        kpis: ["Semelles filantes 50×20 cm"],
        details: ["Soubassement en agglomérés pleins 20 cm"],
      },
      {
        label: "Superstructure",
        description: "Murs en blocs béton avec doublage intérieur.",
        kpis: ["Murs en agglomérés creux 20 cm"],
        details: ["Doublage 13+100 sur ossature métallique"],
      },
    ]);
  });

  it("reads the schema from the schema_ key, the one the backend sends", () => {
    const wire: ProjectSummaryWire = {
      description: "Lot 02 — gros œuvre.",
      systeme_constructif: [
        {
          label: "Infrastructure",
          description: "Fondations superficielles filantes.",
          kpis: ["Semelles filantes 50×20 cm"],
          details: ["Béton C25/30 XC2"],
          schema_: {
            schema_type: "semelle_filante",
            params: { largeur_cm: "50", hauteur_cm: "20" },
          },
        },
      ],
      contraintes: [],
    };

    expect(toProjectSummary(wire).systemeConstructif[0].schema).toEqual({
      schemaType: "semelle_filante",
      params: { largeur_cm: "50", hauteur_cm: "20" },
    });
  });

  it("renders the contraintes in the order the wire sends them", () => {
    const wire: ProjectSummaryWire = {
      description: "Réhabilitation d'un bâtiment tertiaire en site occupé.",
      systeme_constructif: [],
      contraintes: [
        {
          label: "Contraintes de site",
          kpis: ["Accès poids lourds limité"],
          details: ["Voirie communale étroite, giration 12 m"],
        },
        {
          label: "Contraintes réglementaires",
          kpis: ["ERP de 3e catégorie"],
          details: ["Accessibilité PMR sur l'ensemble des circulations"],
        },
        {
          label: "Contraintes de phasage",
          kpis: ["Deux phases"],
          details: ["Travaux en site occupé, maintien de l'exploitation"],
        },
      ],
    };

    expect(toProjectSummary(wire).contraintes.map((c) => c.label)).toEqual([
      "Contraintes de site",
      "Contraintes réglementaires",
      "Contraintes de phasage",
    ]);
  });

  it("copies the kpis and details of a constructive system unaltered", () => {
    const wire: ProjectSummaryWire = {
      description: "Extension d'un atelier de production.",
      systeme_constructif: [
        {
          label: "Infrastructure",
          description: "Fondations et dallage.",
          kpis: [
            "Dallage 15 cm sur terre-plein",
            "Semelles filantes 50×20 cm",
            "Dallage 15 cm sur terre-plein",
          ],
          details: [
            "Drainage périphérique en graviers et géotextile",
            "Béton C25/30 XC2",
            "Drainage périphérique en graviers et géotextile",
          ],
        },
      ],
      contraintes: [],
    };

    const [item] = toProjectSummary(wire).systemeConstructif;

    expect(item.kpis).toEqual([
      "Dallage 15 cm sur terre-plein",
      "Semelles filantes 50×20 cm",
      "Dallage 15 cm sur terre-plein",
    ]);
    expect(item.details).toEqual([
      "Drainage périphérique en graviers et géotextile",
      "Béton C25/30 XC2",
      "Drainage périphérique en graviers et géotextile",
    ]);
  });

  it("renders an empty systemeConstructif when the wire omits the key", () => {
    const wire = malformedWire({
      description: "Réhabilitation lourde d'un bâtiment tertiaire.",
      contraintes: [],
    });

    expect(toProjectSummary(wire).systemeConstructif).toEqual([]);
  });

  it("renders empty contraintes when the wire sends something other than an array", () => {
    const wire = malformedWire({
      description: "Construction d'un hangar agricole.",
      systeme_constructif: [],
      contraintes: "Aucune contrainte particulière relevée au CCTP",
    });

    expect(toProjectSummary(wire).contraintes).toEqual([]);
  });

  it("omits the schema when schema_type is missing or empty", () => {
    const missingType = malformedWire({
      description: "Lot 02 — gros œuvre.",
      systeme_constructif: [
        {
          label: "Infrastructure",
          description: "Fondations superficielles filantes.",
          kpis: ["Semelles filantes 50×20 cm"],
          details: ["Béton C25/30 XC2"],
          schema_: { params: { largeur_cm: "50" } },
        },
      ],
      contraintes: [],
    });
    const emptyType = malformedWire({
      description: "Lot 02 — gros œuvre.",
      systeme_constructif: [
        {
          label: "Infrastructure",
          description: "Fondations superficielles filantes.",
          kpis: ["Semelles filantes 50×20 cm"],
          details: ["Béton C25/30 XC2"],
          schema_: { schema_type: "", params: { largeur_cm: "50" } },
        },
      ],
      contraintes: [],
    });

    const expected = {
      label: "Infrastructure",
      description: "Fondations superficielles filantes.",
      kpis: ["Semelles filantes 50×20 cm"],
      details: ["Béton C25/30 XC2"],
    };

    expect(toProjectSummary(missingType).systemeConstructif[0]).toEqual(
      expected,
    );
    expect(toProjectSummary(emptyType).systemeConstructif[0]).toEqual(expected);
  });

  it("JSON-serialises a non-textual schema param so params stays a Record<string, string>", () => {
    const wire: ProjectSummaryWire = {
      description: "Lot 02 — gros œuvre.",
      systeme_constructif: [
        {
          label: "Infrastructure",
          description: "Fondations superficielles filantes.",
          kpis: ["Semelles filantes 50×20 cm"],
          details: ["Béton C25/30 XC2"],
          schema_: {
            schema_type: "semelle_filante",
            params: {
              type_fondation: "Semelle filante",
              largeur_cm: 50,
              dimensions_cm: ["50", "20"],
            },
          },
        },
      ],
      contraintes: [],
    };

    expect(toProjectSummary(wire).systemeConstructif[0].schema).toEqual({
      schemaType: "semelle_filante",
      params: {
        type_fondation: "Semelle filante",
        largeur_cm: "50",
        dimensions_cm: '["50","20"]',
      },
    });
  });

  it("ignores a schema key without the trailing underscore, which the backend never sends", () => {
    const wire = malformedWire({
      description: "Lot 02 — gros œuvre.",
      systeme_constructif: [
        {
          label: "Infrastructure",
          description: "Fondations superficielles filantes.",
          kpis: ["Semelles filantes 50×20 cm"],
          details: ["Béton C25/30 XC2"],
          schema: {
            schema_type: "semelle_filante",
            params: { largeur_cm: "50" },
          },
        },
      ],
      contraintes: [],
    });

    expect(toProjectSummary(wire).systemeConstructif[0]).toEqual({
      label: "Infrastructure",
      description: "Fondations superficielles filantes.",
      kpis: ["Semelles filantes 50×20 cm"],
      details: ["Béton C25/30 XC2"],
    });
  });

  it("returns an empty string when the wire sends null for a label or a description", () => {
    const wire = malformedWire({
      description: null,
      systeme_constructif: [
        {
          label: null,
          description: null,
          kpis: ["Dallage 15 cm sur terre-plein"],
          details: ["Béton C25/30 XC2"],
        },
      ],
      contraintes: [],
    });

    const result = toProjectSummary(wire);

    expect(result.description).toBe("");
    expect(result.systemeConstructif[0]).toEqual({
      label: "",
      description: "",
      kpis: ["Dallage 15 cm sur terre-plein"],
      details: ["Béton C25/30 XC2"],
    });
  });

  it("returns an empty array when the wire sends null instead of kpis", () => {
    const wire = malformedWire({
      description: "Construction d'un groupe scolaire.",
      systeme_constructif: [
        {
          label: "Infrastructure",
          description: "Fondations superficielles filantes.",
          kpis: null,
          details: ["Béton C25/30 XC2"],
        },
      ],
      contraintes: [],
    });

    expect(toProjectSummary(wire).systemeConstructif[0]).toEqual({
      label: "Infrastructure",
      description: "Fondations superficielles filantes.",
      kpis: [],
      details: ["Béton C25/30 XC2"],
    });
  });

  it("keeps each of the four row statuses the backend reports", async () => {
    const { toSummaryStatus } = await import("./summary.mapper");

    expect(toSummaryStatus("generating")).toBe("generating");
    expect(toSummaryStatus("done")).toBe("done");
    expect(toSummaryStatus("partial")).toBe("partial");
    expect(toSummaryStatus("error")).toBe("error");
  });

  it("falls back to done on a row status the contract does not name", async () => {
    const { toSummaryStatus } = await import("./summary.mapper");

    expect(toSummaryStatus("en_cours")).toBe("done");
    expect(toSummaryStatus(null)).toBe("done");
    expect(toSummaryStatus(undefined)).toBe("done");
  });
});
