import type { ComponentType } from "react";
import { SchemaFouilleRigole } from "./SchemaFouilleRigole";
import { SchemaMulticouche } from "./SchemaMulticouche";
import { SchemaSemelleFilante } from "./SchemaSemelleFilante";

interface SchemaComponentProps {
  params: Record<string, string>;
  schemaType?: string;
}

export const SCHEMA_REGISTRY: Record<
  string,
  ComponentType<SchemaComponentProps>
> = {
  semelle_filante: SchemaSemelleFilante,
  fouille_rigole: SchemaFouilleRigole,
  dallage_terre_plein: SchemaMulticouche,
  plancher_hourdis: SchemaMulticouche,
  plancher_bois: SchemaMulticouche,
  toiture_terrasse: SchemaMulticouche,
  mur_doublage: SchemaMulticouche,
  cloison: SchemaMulticouche,
  charpente_couverture: SchemaMulticouche,
  voirie: SchemaMulticouche,
};
