import { AnimatePresence, motion } from "framer-motion";
import {
  Plus,
  MessageSquare,
  Trash2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useState } from "react";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import type { Conversation } from "../types/types";

interface ConversationSidebarProps {
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  isPending: boolean;
}

/**
 * Sidebar listing conversations.
 * The active conversation is always rendered as a single stable item.
 * Only the title text animates (slide out right → slide in left) when
 * a new conversation gets its real title from the backend.
 */
export function ConversationSidebar({
  conversations,
  selectedId,
  onSelect,
  onNew,
  onDelete,
  isPending,
}: ConversationSidebarProps) {
  const [collapsed, setCollapsed] = useState(false);

  const activeConv = conversations.find((c) => c.id === selectedId);
  const activeTitle = selectedId
    ? (activeConv?.title ?? "Nouvelle conversation")
    : "Nouvelle conversation";

  const otherConversations = conversations.filter((c) => c.id !== selectedId);

  return (
    <aside
      className={cn(
        "flex h-full shrink-0 flex-col border-r border-[hsl(var(--border))] bg-[hsl(var(--background))] transition-[width] duration-200",
        collapsed ? "w-12" : "w-64",
      )}
    >
      <header
        className={cn(
          "flex shrink-0 items-center py-3",
          collapsed ? "justify-center px-2" : "justify-between px-4",
        )}
      >
        {!collapsed && <h2 className="text-sm font-semibold">Conversations</h2>}
        <div className="flex items-center gap-1">
          {!collapsed && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onNew}
              aria-label="Nouvelle conversation"
              className="h-8 w-8 p-0"
            >
              <Plus className="h-4 w-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCollapsed((prev) => !prev)}
            aria-label={collapsed ? "Ouvrir le panneau" : "Fermer le panneau"}
            className="h-8 w-8 p-0"
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </Button>
        </div>
      </header>

      {collapsed ? (
        <nav className="flex flex-col items-center gap-1 pt-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={onNew}
            aria-label="Nouvelle conversation"
            className="h-8 w-8 p-0"
          >
            <Plus className="h-4 w-4" />
          </Button>
          {conversations.map((conv) => (
            <button
              key={conv.id}
              type="button"
              onClick={() => onSelect(conv.id)}
              aria-label={conv.title}
              title={conv.title}
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-md transition-colors",
                conv.id === selectedId
                  ? "bg-[hsl(var(--secondary))] text-[hsl(var(--primary))]"
                  : "text-muted-foreground hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]",
              )}
            >
              <MessageSquare className="h-4 w-4" />
            </button>
          ))}
        </nav>
      ) : (
        <nav className="flex-1 overflow-y-auto">
          {isPending && (
            <div className="flex justify-center py-4">
              <LoadingSpinner size="sm" />
            </div>
          )}

          <ul>
            {/* Active conversation — single stable <li>, only text animates */}
            <li
              className="flex w-full items-start gap-2 px-4 py-2 text-left text-sm bg-[hsl(var(--secondary))] text-[hsl(var(--primary))]"
              aria-current="true"
            >
              <MessageSquare className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="flex-1 min-w-0">
                <span className="block truncate overflow-hidden relative">
                  <AnimatePresence mode="popLayout" initial={false}>
                    <motion.span
                      key={activeTitle}
                      initial={{ x: "-100%", opacity: 0 }}
                      animate={{ x: 0, opacity: 1 }}
                      exit={{ x: "100%", opacity: 0 }}
                      transition={{ duration: 0.25, ease: "easeInOut" }}
                      className="inline-block"
                    >
                      {activeTitle}
                    </motion.span>
                  </AnimatePresence>
                </span>
              </div>
              {selectedId && (
                <button
                  type="button"
                  onClick={() => onDelete(selectedId)}
                  aria-label={`Supprimer ${activeTitle}`}
                  className="group/del mt-0.5 shrink-0 hover:scale-110 transition-all"
                >
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground group-hover/del:!text-red-500 transition-colors" />
                </button>
              )}
            </li>

            {/* Other conversations */}
            {otherConversations.map((conv) => (
              <li
                key={conv.id}
                className={cn(
                  "group flex w-full items-start gap-2 pr-4 text-sm transition-colors",
                  "text-muted-foreground hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]",
                )}
              >
                <button
                  type="button"
                  onClick={() => onSelect(conv.id)}
                  className="flex min-w-0 flex-1 cursor-pointer items-start gap-2 py-2 pl-4 text-left"
                >
                  <MessageSquare className="mt-0.5 h-4 w-4 shrink-0" />
                  <span className="block truncate">{conv.title}</span>
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(conv.id)}
                  aria-label={`Supprimer ${conv.title}`}
                  className="group/del mt-0.5 shrink-0 opacity-0 group-hover:opacity-100 hover:scale-110 transition-all"
                >
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground group-hover/del:!text-red-500 transition-colors" />
                </button>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </aside>
  );
}
