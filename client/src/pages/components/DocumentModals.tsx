import { DeleteDocumentModal, DocumentInfoModal } from "@/features/projects";
import type { Document } from "@/features/projects";

interface DocumentModalsProps {
  deleteTarget: Document | null;
  onDeleteTargetChange: (doc: Document | null) => void;
  onConfirmDelete: (id: string) => void;
  isDeleting: boolean;
  previewDoc: Document | null;
  onPreviewDocChange: (doc: Document | null) => void;
}

export function DocumentModals({
  deleteTarget,
  onDeleteTargetChange,
  onConfirmDelete,
  isDeleting,
  previewDoc,
  onPreviewDocChange,
}: DocumentModalsProps) {
  return (
    <>
      {deleteTarget && (
        <DeleteDocumentModal
          filename={deleteTarget.filename}
          isPending={isDeleting}
          onConfirm={() => onConfirmDelete(deleteTarget.id)}
          onClose={() => onDeleteTargetChange(null)}
        />
      )}

      {previewDoc && (
        <DocumentInfoModal
          document={previewDoc}
          onClose={() => onPreviewDocChange(null)}
        />
      )}
    </>
  );
}
