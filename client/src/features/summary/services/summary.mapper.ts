import type {
  ContrainteItem,
  ProjectSummaryData,
  SummarySchemaData,
  SummaryStatus,
  SystemeConstructifItem,
} from "../types/types";

/**
 * Crosses the summary from the wire into the domain.
 *
 * The only place snake_case becomes camelCase. Takes `unknown`, and that is the
 * honest signature: the cached summary comes back from
 * `GET /projects/{id}/summary` through an unchecked `apiGet<T>` cast, so nothing
 * guarantees its shape. A missing or null field must not take the tab down.
 */
export function toProjectSummary(raw: unknown): ProjectSummaryData {
  const wire = record(raw);

  return {
    description: text(wire.description),
    systemeConstructif: list(wire.systeme_constructif).map(toSystemeConstructif),
    contraintes: list(wire.contraintes).map(toContrainte),
  };
}

function toSystemeConstructif(raw: unknown): SystemeConstructifItem {
  const item = record(raw);

  return {
    label: text(item.label),
    description: text(item.description),
    kpis: strings(item.kpis),
    details: strings(item.details),
    schema: toSchema(item.schema_),
  };
}

function toContrainte(raw: unknown): ContrainteItem {
  const item = record(raw);

  return {
    label: text(item.label),
    kpis: strings(item.kpis),
    details: strings(item.details),
  };
}

function toSchema(raw: unknown): SummarySchemaData | undefined {
  const schema = record(raw);
  const schemaType = text(schema.schema_type);
  if (!schemaType) return undefined;

  const params: Record<string, string> = {};
  for (const [key, value] of Object.entries(record(schema.params))) {
    params[key] = typeof value === "string" ? value : JSON.stringify(value);
  }

  return { schemaType, params };
}

const SUMMARY_STATUSES: readonly SummaryStatus[] = [
  "generating",
  "done",
  "partial",
  "error",
];

/**
 * Narrows the row status the wire reports.
 *
 * Nothing validates `GET /projects/{id}/summary`, so an unknown value is
 * possible. It maps to `done`, which renders no banner — the same thing the UI
 * did with an unrecognised string before this feature existed.
 */
export function toSummaryStatus(raw: unknown): SummaryStatus {
  return SUMMARY_STATUSES.find((status) => status === raw) ?? "done";
}

function record(raw: unknown): Record<string, unknown> {
  return raw !== null && typeof raw === "object"
    ? (raw as Record<string, unknown>)
    : {};
}

function list(raw: unknown): unknown[] {
  return Array.isArray(raw) ? raw : [];
}

function strings(raw: unknown): string[] {
  return Array.isArray(raw) ? raw.map(text) : [];
}

function text(raw: unknown): string {
  return typeof raw === "string" ? raw : "";
}
