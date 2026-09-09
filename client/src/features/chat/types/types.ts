export interface Source {
  document_id: string;
  filename: string;
  page: number;
  lot: string;
  phase: string;
  text: string;
}

export interface StructuredTable {
  title: string;
  columns: string[];
  rows: Record<string, string>[];
}

export interface StructuredSchema {
  schema_type: string;
  title: string;
  params: Record<string, string>;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  structured: StructuredTable | null;
  schema: StructuredSchema | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  project_id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationList {
  conversations: Conversation[];
  total: number;
}

/** Local-only message used during streaming before persistence. */
export interface StreamingMessage {
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  structured: StructuredTable | null;
  schema: StructuredSchema | null;
  created_at?: string;
}
