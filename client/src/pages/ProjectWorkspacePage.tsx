import { ArrowLeft, Info, BookOpen, FileText, MessageSquare } from "lucide-react";
import { useState, useCallback, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { ChatPanel, ConversationSidebar } from "@/features/chat";
import {
  useProject,
  useUpdateProject,
  ProjectInfoForm,
} from "@/features/projects";
import type { Document, Folder } from "@/features/projects";
import { usePendingFolderUploadStore } from "@/features/projects/stores/pendingFolderUploadStore";
import { ProjectSummaryTab } from "@/features/summary/components/ProjectSummaryTab";
import { useTopbarStore } from "@/lib/store/topbarStore";
import { WorkspaceDocumentsTab } from "./components/WorkspaceDocumentsTab";
import {
  WorkspaceModals,
  type ContextMenuTarget,
} from "./components/WorkspaceModals";
import { useWorkspaceChat } from "./hooks/useWorkspaceChat";
import { useWorkspaceDocuments } from "./hooks/useWorkspaceDocuments";
import { useWorkspaceDragDrop } from "./hooks/useWorkspaceDragDrop";

type Tab = "info" | "summary" | "documents" | "chat";

export function ProjectWorkspacePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const hasPendingUpload = usePendingFolderUploadStore((s) => s.pending !== null);
  const [tab, setTab] = useState<Tab>(hasPendingUpload ? "documents" : "info");

  // --- Project data ---
  const project = useProject(projectId!);
  const updateProject = useUpdateProject(projectId!);

  // --- Topbar title ---
  const setTopbarTitle = useTopbarStore((s) => s.setTitle);
  useEffect(() => {
    if (project.data?.name) setTopbarTitle(project.data.name);
    return () => setTopbarTitle(null);
  }, [project.data?.name, setTopbarTitle]);

  // --- Documents ---
  const docs = useWorkspaceDocuments(projectId!);

  // --- Consume pending folder upload from projects page drop ---
  const consumePending = usePendingFolderUploadStore((s) => s.consume);
  useEffect(() => {
    if (!project.data) return;
    const pending = consumePending();
    if (pending && pending.files.length > 0) {
      docs.uploadFolder.mutate({
        folderName: pending.folderName,
        files: pending.files,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.data?.id]);

  // --- Chat ---
  const chatState = useWorkspaceChat(projectId!);

  // --- Modal state ---
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null);
  const [deleteFolderTarget, setDeleteFolderTarget] = useState<Folder | null>(
    null,
  );
  const [editFolderTarget, setEditFolderTarget] = useState<Folder | null>(null);
  const [editingFolderId, setEditingFolderId] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null);
  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [contextMenu, setContextMenu] = useState<{
    position: { x: number; y: number };
    target: ContextMenuTarget;
  } | null>(null);

  // --- Drag & drop ---
  const handleFileDropOnBody = useCallback(
    (files: File[]) => {
      files.forEach((file) => {
        if (docs.currentFolderId) {
          docs.uploadDocToFolder.mutate({
            file,
            uploadId: crypto.randomUUID(),
            folderId: docs.currentFolderId,
          });
        } else {
          docs.uploadDoc.mutate({ file, uploadId: crypto.randomUUID() });
        }
      });
    },
    [docs.uploadDoc, docs.uploadDocToFolder, docs.currentFolderId],
  );

  const handleFolderDrop = useCallback(
    (folderName: string, files: File[]) => {
      docs.uploadFolder.mutate({ folderName, files });
    },
    [docs.uploadFolder],
  );

  const dragDrop = useWorkspaceDragDrop({
    onFileDropOnBody: handleFileDropOnBody,
    onFolderDrop: handleFolderDrop,
  });

  const { resetDragState } = dragDrop;

  const handleFileDropOnFolder = useCallback(
    (files: File[], folderId: string) => {
      resetDragState();
      files.forEach((file) => {
        docs.uploadDocToFolder.mutate({
          file,
          uploadId: crypto.randomUUID(),
          folderId,
        });
      });
    },
    [docs.uploadDocToFolder, resetDragState],
  );

  // --- Context menu ---
  const handleContextMenu = useCallback(
    (e: React.MouseEvent, target: ContextMenuTarget): void => {
      setContextMenu({ position: { x: e.clientX, y: e.clientY }, target });
    },
    [],
  );

  // --- Loading / Error ---
  if (project.isPending) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (project.error)
    return (
      <ErrorMessage error={project.error} onRetry={() => void project.refetch()} />
    );
  if (!project.data) return null;

  return (
    <main className="flex flex-col -m-4 md:-m-6 h-[calc(100vh-3.5rem)] md:h-[calc(100vh-4rem)]">
      {/* Header + Tabs */}
      <nav className="flex items-center gap-1 px-6 border-b border-[hsl(var(--border))]">
        <Link
          to="/projects"
          aria-label="Retour aux projets"
          className="group mr-3 flex h-8 w-8 items-center justify-center text-muted-foreground transition-colors hover:text-[#FFC300] shrink-0"
        >
          <ArrowLeft className="h-5 w-5 transition-transform group-hover:scale-110" />
        </Link>
        <button
          type="button"
          onClick={() => setTab("info")}
          className={`inline-flex items-center gap-2 px-3 py-2.5 text-sm font-medium rounded-t-md transition-colors ${
            tab === "info"
              ? "text-[#FFC300]"
              : "text-muted-foreground hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]"
          }`}
        >
          <Info className="h-4 w-4" />
          Info
        </button>
        <button
          type="button"
          onClick={() => setTab("summary")}
          className={`inline-flex items-center gap-2 px-3 py-2.5 text-sm font-medium rounded-t-md transition-colors ${
            tab === "summary"
              ? "text-[#FFC300]"
              : "text-muted-foreground hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]"
          }`}
        >
          <BookOpen className="h-4 w-4" />
          Résumé
        </button>
        <button
          type="button"
          onClick={() => setTab("documents")}
          className={`inline-flex items-center gap-2 px-3 py-2.5 text-sm font-medium rounded-t-md transition-colors ${
            tab === "documents"
              ? "text-[#FFC300]"
              : "text-muted-foreground hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]"
          }`}
        >
          <FileText className="h-4 w-4" />
          Documents
        </button>
        <button
          type="button"
          onClick={() => setTab("chat")}
          className={`inline-flex items-center gap-2 px-3 py-2.5 text-sm font-medium rounded-t-md transition-colors ${
            tab === "chat"
              ? "text-[#FFC300]"
              : "text-muted-foreground hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]"
          }`}
        >
          <MessageSquare className="h-4 w-4" />
          Chat
          {chatState.chat.isStreaming && tab !== "chat" && (
            <span className="h-2 w-2 rounded-full bg-[#FFC300] animate-pulse" />
          )}
        </button>
      </nav>

      {/* Tab content */}
      <div className="min-h-0 flex-1 overflow-hidden">
        {tab === "info" && (
          <section
            className="h-full overflow-y-auto p-6"
            aria-label="Informations du projet"
          >
            <ProjectInfoForm
              project={project.data}
              onSubmit={(data) => updateProject.mutate(data)}
              isPending={updateProject.isPending}
            />
          </section>
        )}

        {tab === "summary" && (
          <ProjectSummaryTab
            projectId={projectId!}
            projectName={project.data.name}
          />
        )}

        {tab === "documents" && (
          <WorkspaceDocumentsTab
            projectId={projectId!}
            sortedDocuments={docs.sortedDocuments}
            sortField={docs.sortField}
            sortDirection={docs.sortDirection}
            onSort={docs.handleSort}
            search={docs.search}
            onSearchChange={docs.setSearch}
            summary={docs.summary}
            currentFolderId={docs.currentFolderId}
            onOpenFolder={docs.setCurrentFolderId}
            currentFolder={docs.currentFolder}
            folderOptions={docs.folderOptions}
            selectedIds={docs.selectedIds}
            onToggleSelect={docs.toggle}
            onToggleSelectAll={docs.toggleAll}
            onDeleteDocument={(doc) => setDeleteTarget(doc)}
            onMoveDocument={docs.handleMoveDocument}
            onDeleteFolder={setDeleteFolderTarget}
            onRenameFolder={(folderId, name) =>
              docs.updateFolderMut.mutate({ folderId, name })
            }
            isRenamingFolder={docs.updateFolderMut.isPending}
            onShowCreateFolder={() => setShowCreateFolder(true)}
            externalDragOver={dragDrop.externalDragOver}
            onSectionDragEnter={dragDrop.handleSectionDragEnter}
            onSectionDragOver={dragDrop.handleSectionDragOver}
            onSectionDragLeave={dragDrop.handleSectionDragLeave}
            onSectionDrop={dragDrop.handleSectionDrop}
            onFileDropOnFolder={handleFileDropOnFolder}
            onContextMenu={handleContextMenu}
            editingFolderIdExternal={editingFolderId}
            onEditingFolderIdChange={setEditingFolderId}
            isDocsPending={docs.documents.isPending}
            docsError={docs.documents.error}
            hasDocuments={(docs.documents.data?.documents.length ?? 0) > 0}
            hasFolders={(docs.folders.data?.folders.length ?? 0) > 0}
          />
        )}

        {tab === "chat" && (
          <section
            className="flex h-full overflow-hidden"
            aria-label="Chat du projet"
          >
            <ConversationSidebar
              conversations={chatState.conversations.data?.conversations ?? []}
              selectedId={chatState.sidebarConvId}
              onSelect={chatState.handleSelectConversation}
              onNew={chatState.handleNewConversation}
              onDelete={chatState.handleDeleteConversation}
              isPending={chatState.conversations.isPending}
            />

            <div className="min-h-0 min-w-0 flex-1">
              <ChatPanel
                historyMessages={
                  chatState.chat.messages.length > 0
                    ? []
                    : (chatState.messages.data ?? [])
                }
                streamingMessages={chatState.chat.messages}
                isStreaming={chatState.chat.isStreaming}
                isPending={
                  !!chatState.selectedConvId &&
                  chatState.messages.isPending &&
                  chatState.chat.messages.length === 0
                }
                error={chatState.messages.error}
                onSend={chatState.handleSend}
              />
            </div>
          </section>
        )}
      </div>

      {/* Modals */}
      <WorkspaceModals
        deleteTarget={deleteTarget}
        onDeleteTargetChange={setDeleteTarget}
        onConfirmDelete={(id) => {
          docs.deleteDoc.mutate(id, {
            onSuccess: () => setDeleteTarget(null),
          });
        }}
        isDeleting={docs.deleteDoc.isPending}
        showCreateFolder={showCreateFolder}
        onShowCreateFolderChange={setShowCreateFolder}
        onConfirmCreateFolder={(data) => {
          docs.createFolderMut.mutate(data, {
            onSuccess: () => setShowCreateFolder(false),
          });
        }}
        isCreatingFolder={docs.createFolderMut.isPending}
        deleteFolderTarget={deleteFolderTarget}
        onDeleteFolderTargetChange={setDeleteFolderTarget}
        onConfirmDeleteFolder={(id) => {
          docs.deleteFolderMut.mutate(id, {
            onSuccess: () => setDeleteFolderTarget(null),
          });
        }}
        isDeletingFolder={docs.deleteFolderMut.isPending}
        currentFolderId={docs.currentFolderId}
        onCurrentFolderIdChange={docs.setCurrentFolderId}
        editFolderTarget={editFolderTarget}
        onEditFolderTargetChange={setEditFolderTarget}
        onConfirmEditFolder={(data) => {
          docs.updateFolderMut.mutate(data, {
            onSuccess: () => setEditFolderTarget(null),
          });
        }}
        isEditingFolder={docs.updateFolderMut.isPending}
        previewDoc={previewDoc}
        onPreviewDocChange={setPreviewDoc}
        contextMenu={contextMenu}
        onContextMenuClose={() => setContextMenu(null)}
        onEditingFolderIdChange={setEditingFolderId}
        selectedIds={docs.selectedIds}
        onToggleSelect={docs.toggle}
        selectionCount={docs.count()}
        folders={docs.folderOptions}
        onMoveSelected={docs.handleBatchMove}
        onDeleteSelected={docs.handleBatchDelete}
        onClearSelection={docs.clear}
      />
    </main>
  );
}
