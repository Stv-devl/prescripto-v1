import { motion } from "framer-motion";
import type { StructuredSchema } from "../types/types";
import { SCHEMA_REGISTRY } from "./schemas";

interface ChatStructuredSchemaProps {
  schema: StructuredSchema;
  delay?: number;
}

/**
 * Renders a parametric SVG schema from RAG extraction.
 * Looks up the component in SCHEMA_REGISTRY by schema_type.
 * Appears after the table if both are present (via delay prop).
 */
export function ChatStructuredSchema({
  schema,
  delay = 0,
}: ChatStructuredSchemaProps) {
  const SchemaComponent = SCHEMA_REGISTRY[schema.schema_type];

  if (!SchemaComponent) {
    return null;
  }

  return (
    <motion.figure
      className="h-0 mt-0 overflow-hidden opacity-0"
      initial={{ opacity: 0, height: 0, marginTop: 0 }}
      animate={{ opacity: 1, height: "auto", marginTop: 12 }}
      transition={{ duration: 0.7, delay, ease: "easeOut" }}
    >
      <motion.figcaption
        className="mb-2 text-xs font-semibold text-[hsl(var(--muted-foreground))]"
        style={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay }}
      >
        {schema.title}
      </motion.figcaption>
      <SchemaComponent params={schema.params} schemaType={schema.schema_type} />
    </motion.figure>
  );
}
