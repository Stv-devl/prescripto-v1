import { useState } from "react";
import {
  useCreateFolder,
  useDeleteDocument,
  useDeleteFolder,
  useDocuments,
  useFolders,
  useSelectionStore,
  useUploadDocument,
  useUploadDocumentToFolder,
  useUploadFolder,
  useUploadStore,
  useMoveDocument,
  useUpdateFolder,
} from "@/features/projects";
import { useBatchDocumentActions } from "./useBatchDocumentActions";
import { useDocumentsSummary } from "./useDocumentsSummary";
import { useFolderSelection } from "./useFolderSelection";
import { usePendingUploadDocs } from "./usePendingUploadDocs";
import { useSortedDocuments } from "./useSortedDocuments";
import { useUploadCleanup } from "./useUploadCleanup";

/**
 * Encapsulates all documents state, sorting, filtering, and mutations
 * for the ProjectWorkspacePage documents tab.
 */
export function useWorkspaceDocuments(projectId: string) {
  const [search, setSearch] = useState("");

  const { selectedIds, toggle, toggleAll, clear, count } = useSelectionStore();
  const uploads = useUploadStore((s) => s.uploads);
  const removeUpload = useUploadStore((s) => s.removeUpload);

  const documents = useDocuments(projectId);
  const deleteDoc = useDeleteDocument(projectId);
  const uploadDoc = useUploadDocument(projectId);
  const uploadDocToFolder = useUploadDocumentToFolder(projectId);
  const uploadFolder = useUploadFolder(projectId);
  const folders = useFolders(projectId);
  const createFolderMut = useCreateFolder(projectId);
  const updateFolderMut = useUpdateFolder(projectId);
  const deleteFolderMut = useDeleteFolder(projectId);
  const moveDocMut = useMoveDocument(projectId);

  const { currentFolderId, setCurrentFolderId, currentFolder, folderOptions } =
    useFolderSelection(folders, clear);

  useUploadCleanup(uploads, documents.data?.documents, removeUpload);

  const pendingUploadDocs = usePendingUploadDocs(uploads, currentFolderId, projectId);

  const { sortField, sortDirection, sortedDocuments, handleSort } = useSortedDocuments(
    documents.data?.documents,
    currentFolderId,
    search,
    pendingUploadDocs,
  );

  const summary = useDocumentsSummary(documents.data?.documents);

  const { handleMoveDocument, handleBatchDelete, handleBatchMove } =
    useBatchDocumentActions({ selectedIds, deleteDoc, moveDocMut, clear });

  return {
    sortField,
    sortDirection,
    search,
    setSearch,
    currentFolderId,
    setCurrentFolderId,
    currentFolder,
    sortedDocuments,
    summary,
    folderOptions,
    pendingUploadDocs,

    selectedIds,
    toggle,
    toggleAll,
    clear,
    count,

    documents,
    folders,

    deleteDoc,
    uploadDoc,
    uploadDocToFolder,
    uploadFolder,
    createFolderMut,
    updateFolderMut,
    deleteFolderMut,

    handleSort,
    handleMoveDocument,
    handleBatchDelete,
    handleBatchMove,
  } as const;
}
