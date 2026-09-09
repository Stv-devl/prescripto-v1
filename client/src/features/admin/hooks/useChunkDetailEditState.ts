import { useRef, useState } from "react";

interface ChunkDetailEditState {
  isEditing: boolean;
  setIsEditing: (editing: boolean) => void;
  editText: string;
  setEditText: (text: string) => void;
  showDeleteConfirm: boolean;
  setShowDeleteConfirm: (show: boolean) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}

/** The edit-mode and delete-confirmation local state `ChunkDetail` owns. */
export function useChunkDetailEditState(): ChunkDetailEditState {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  return {
    isEditing,
    setIsEditing,
    editText,
    setEditText,
    showDeleteConfirm,
    setShowDeleteConfirm,
    textareaRef,
  };
}
