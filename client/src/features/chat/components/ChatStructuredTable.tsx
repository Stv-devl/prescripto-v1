import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { StructuredTable } from "../types/types";

interface ChatStructuredTableProps {
  table: StructuredTable;
}

/**
 * Renders a structured data table from RAG extraction.
 * Rows appear one by one (opacity), matching the streaming text feel.
 */
export function ChatStructuredTable({ table }: ChatStructuredTableProps) {
  const keys = table.rows.length > 0 ? Object.keys(table.rows[0]) : [];

  return (
    <motion.figure
      className="h-0 mt-0 overflow-hidden opacity-0"
      initial={{ opacity: 0, height: 0, marginTop: 0 }}
      animate={{ opacity: 1, height: "auto", marginTop: 12 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
    >
      <motion.figcaption
        className="mb-2 text-xs font-semibold text-[hsl(var(--muted-foreground))]"
        style={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6 }}
      >
        {table.title}
      </motion.figcaption>
      <table className="w-full border-collapse text-xs">
        <motion.thead
          style={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <tr>
            {table.columns.map((col) => (
              <th
                key={col}
                className="border border-[hsl(var(--border))] bg-[hsl(var(--muted))] px-2 py-1.5 text-left font-semibold"
              >
                {col}
              </th>
            ))}
          </tr>
        </motion.thead>
        <tbody>
          {table.rows.map((row, i) => (
            <motion.tr
              key={i}
              className={cn(i % 2 === 1 && "bg-[hsl(var(--muted)/0.3)]")}
              style={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.4 + i * 0.18 }}
            >
              {keys.map((key, j) => {
                const value = row[key] ?? "—";
                const isEmpty = value === "—";
                return (
                  <td
                    key={key}
                    className={cn(
                      "border border-[hsl(var(--border))] px-2 py-1.5",
                      j === 0 && "font-medium",
                      isEmpty && "text-[hsl(var(--muted-foreground))]",
                    )}
                  >
                    {value}
                  </td>
                );
              })}
            </motion.tr>
          ))}
        </tbody>
      </table>
    </motion.figure>
  );
}
