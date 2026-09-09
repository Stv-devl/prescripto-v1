/**
 * Two shapes, and they are not the same one.
 *
 * `*Wire` is what `backend/app/schemas/summary.py` actually serialises:
 * snake_case, and the schema key is `schema_` with its trailing underscore.
 * The unsuffixed types are the domain the UI reads, and `summary.mapper.ts` is
 * the only crossing between them.
 */

/** Schema descriptor as the backend serialises it. */
export interface SummarySchemaWire {
  schema_type: string;
  params: Record<string, unknown>;
}

/** Constructive-system entry as the backend serialises it. */
export interface SystemeConstructifWire {
  label: string;
  description: string;
  kpis: string[];
  details: string[];
  schema_?: SummarySchemaWire | null;
}

/** Constraint entry as the backend serialises it. */
export interface ContrainteWire {
  label: string;
  kpis: string[];
  details: string[];
}

/** Summary payload as the backend serialises it. */
export interface ProjectSummaryWire {
  description: string;
  systeme_constructif: SystemeConstructifWire[];
  contraintes: ContrainteWire[];
}

/** Summary row as `GET /projects/{id}/summary` returns it. */
export interface SummaryReadWire {
  id: string;
  project_id: string;
  status: string;
  data: ProjectSummaryWire | null;
  error_message: string | null;
  generated_at: string | null;
}

/** Schema descriptor as the UI reads it. */
export interface SummarySchemaData {
  schemaType: string;
  params: Record<string, string>;
}

/** Constructive-system entry as the UI reads it. */
export interface SystemeConstructifItem {
  label: string;
  description: string;
  kpis: string[];
  details: string[];
  schema?: SummarySchemaData;
}

/** Constraint entry as the UI reads it. */
export interface ContrainteItem {
  label: string;
  kpis: string[];
  details: string[];
}

/** Summary payload as the UI reads it. */
export interface ProjectSummaryData {
  description: string;
  systemeConstructif: SystemeConstructifItem[];
  contraintes: ContrainteItem[];
}

/** The four states a summary row can be in. */
export type SummaryStatus = "generating" | "done" | "partial" | "error";

/** Summary row after the mapper has crossed it into the domain. */
export interface SummaryRead {
  id: string;
  project_id: string;
  status: SummaryStatus;
  data: ProjectSummaryData | null;
  error_message: string | null;
  generated_at: string | null;
}

/** Whether the project has documents and a cached summary. */
export interface SummaryStatusRead {
  has_documents: boolean;
  has_summary: boolean;
  status: string | null;
}

/** One section finished, as `summary.py:946` emits it. */
export interface SummaryProgressEvent {
  type: "progress";
  section: string;
  index: number;
  total: number;
  status: "done" | "error" | "skipped";
}

/** The assembled summary, as `summary.py:1132` emits it. */
export interface SummaryCompleteEvent {
  type: "complete";
  summary: ProjectSummaryData;
  status: Exclude<SummaryStatus, "generating">;
}

/** A generation failure, as `summary.py:667,715` emits it. */
export interface SummaryErrorEvent {
  type: "error";
  message: string;
}

/** Every event the summary stream can carry. */
export type SummarySSEEvent =
  | SummaryProgressEvent
  | SummaryCompleteEvent
  | SummaryErrorEvent;
