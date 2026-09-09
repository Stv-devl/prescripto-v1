import { z } from "zod";

export const coucheSchema = z.object({
  nom: z.string(),
  epaisseur: z.string(),
  nature: z.string(),
});

export type Couche = z.infer<typeof coucheSchema>;

export const NATURE_COLORS: Record<string, string> = {
  beton: "#c8c8c8",
  beton_arme: "#b0b0b0",
  chape: "#d6cdb7",
  mortier: "#d4c8a8",
  isolant_thermique: "#ffe08a",
  isolant_acoustique: "#b8d4a8",
  etancheite: "#2a2a2a",
  pare_vapeur: "#6eb4d1",
  film_pe: "#a0d8ef",
  revetement: "#e8c9a0",
  carrelage: "#e6d5c3",
  enduit: "#f0e6d3",
  plaque_platre: "#f5f0e8",
  bois: "#d4a56a",
  metal: "#9aa8b8",
  gravier: "#c9bfa6",
  enrobe: "#4a4a4a",
  grave: "#b8a88a",
  hourdis: "#c2b8a4",
  geotextile: "#8cb89c",
  tuile: "#c47a5a",
  ecran_sous_toiture: "#7a9ab0",
  ossature_isolant: "#ffe08a",
};

export const NATURE_PATTERNS: Record<string, string> = {
  beton: "pattern-beton",
  beton_arme: "pattern-beton-arme",
  chape: "pattern-chape",
  mortier: "pattern-mortier",
  isolant_thermique: "pattern-isolant-thermique",
  isolant_acoustique: "pattern-isolant-acoustique",
  etancheite: "pattern-etancheite",
  pare_vapeur: "pattern-pare-vapeur",
  film_pe: "pattern-film-pe",
  revetement: "pattern-revetement",
  carrelage: "pattern-carrelage",
  enduit: "pattern-enduit",
  plaque_platre: "pattern-plaque-platre",
  bois: "pattern-bois",
  metal: "pattern-metal",
  gravier: "pattern-gravier",
  enrobe: "pattern-enrobe",
  grave: "pattern-grave",
  hourdis: "pattern-hourdis",
  geotextile: "pattern-geotextile",
  tuile: "pattern-tuile",
  ecran_sous_toiture: "pattern-ecran-sous-toiture",
  ossature_isolant: "pattern-ossature-isolant",
};

export interface SchemaConfig {
  orientation: "vertical" | "horizontal";
  label: string;
}

export const SCHEMA_CONFIG: Record<string, SchemaConfig> = {
  dallage_terre_plein: {
    orientation: "vertical",
    label: "Dallage sur terre-plein",
  },
  plancher_hourdis: {
    orientation: "vertical",
    label: "Plancher hourdis",
  },
  plancher_bois: {
    orientation: "vertical",
    label: "Plancher bois",
  },
  toiture_terrasse: {
    orientation: "vertical",
    label: "Toiture terrasse",
  },
  mur_doublage: {
    orientation: "horizontal",
    label: "Mur avec doublage",
  },
  cloison: {
    orientation: "horizontal",
    label: "Cloison de distribution",
  },
  charpente_couverture: {
    orientation: "vertical",
    label: "Charpente et couverture",
  },
  voirie: {
    orientation: "vertical",
    label: "Voirie",
  },
};
