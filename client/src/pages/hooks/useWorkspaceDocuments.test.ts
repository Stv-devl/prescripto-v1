import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ok } from "@/lib/result";
import { createQueryClientWrapper } from "@/test/utils";
import type { Document, Folder } from "@/features/projects";
import { useSelectionStore } from "@/features/projects/stores/selectionStore";
import { useUploadStore } from "@/features/projects/stores/uploadStore";
import * as projectsService from "@/features/projects/services/projects.service";
import { useWorkspaceDocuments } from "./useWorkspaceDocuments";

vi.mock("@/features/projects/services/projects.service");

function makeDoc(overrides: Partial<Document>): Document {
  return {
    id: "doc-1",
    project_id: "p-1",
    folder_id: null,
    filename: "a.pdf",
    type: "cctp",
    lot: "03",
    phase: "execution",
    size: 1000,
    status: "ready",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const folder: Folder = {
  id: "folder-1",
  project_id: "p-1",
  name: "Lot 3",
  lot: "03",
  phase: "execution",
  document_count: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  useSelectionStore.getState().clear();
  useUploadStore.getState().reset();
  vi.mocked(projectsService.listFolders).mockResolvedValue(
    ok({ folders: [folder], total: 1 }),
  );
});

describe("useWorkspaceDocuments — comportement principal", () => {
  it("filtre par dossier courant, puis par recherche, puis trie", async () => {
    const docA = makeDoc({ id: "a", filename: "Zebre.pdf", folder_id: null, created_at: "2026-01-01T00:00:00Z" });
    const docB = makeDoc({ id: "b", filename: "Alpha.pdf", folder_id: null, created_at: "2026-01-02T00:00:00Z" });
    const docInFolder = makeDoc({ id: "c", filename: "Dans-dossier.pdf", folder_id: "folder-1" });
    vi.mocked(projectsService.listDocuments).mockResolvedValue(
      ok({ documents: [docA, docB, docInFolder], total: 3 }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });

    await waitFor(() => {
      expect(result.current.sortedDocuments.map((d) => d.id)).toEqual(["b", "a"]);
    });
  });

  it("filtre par le texte de recherche sur le nom, le type, le lot et la phase", async () => {
    const docA = makeDoc({ id: "a", filename: "Zebre.pdf" });
    const docB = makeDoc({ id: "b", filename: "Alpha.pdf" });
    vi.mocked(projectsService.listDocuments).mockResolvedValue(
      ok({ documents: [docA, docB], total: 2 }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(result.current.sortedDocuments).toHaveLength(2));

    act(() => result.current.setSearch("zebre"));

    await waitFor(() => {
      expect(result.current.sortedDocuments.map((d) => d.id)).toEqual(["a"]);
    });
  });

  it("filtre par dossier courant quand currentFolderId est non nul", async () => {
    const inFolder = makeDoc({ id: "a", filename: "Dans-dossier.pdf", folder_id: "folder-1" });
    const otherFolder = makeDoc({ id: "b", filename: "Autre-dossier.pdf", folder_id: "folder-2" });
    const atRoot = makeDoc({ id: "c", filename: "Racine.pdf", folder_id: null });
    vi.mocked(projectsService.listDocuments).mockResolvedValue(
      ok({ documents: [inFolder, otherFolder, atRoot], total: 3 }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(result.current.sortedDocuments).toHaveLength(1));

    act(() => result.current.setCurrentFolderId("folder-1"));

    await waitFor(() => {
      expect(result.current.sortedDocuments.map((d) => d.id)).toEqual(["a"]);
    });
  });

  it("trie par taille croissante quand sortField vaut size et sortDirection asc", async () => {
    const big = makeDoc({ id: "big", filename: "b.pdf", size: 3000 });
    const small = makeDoc({ id: "small", filename: "s.pdf", size: 1000 });
    const medium = makeDoc({ id: "medium", filename: "m.pdf", size: 2000 });
    vi.mocked(projectsService.listDocuments).mockResolvedValue(
      ok({ documents: [big, small, medium], total: 3 }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(result.current.sortedDocuments).toHaveLength(3));

    act(() => result.current.handleSort("size"));

    await waitFor(() => {
      expect(result.current.sortedDocuments.map((d) => d.id)).toEqual([
        "small",
        "medium",
        "big",
      ]);
    });
  });

  it("trie par nom alphabétique quand sortField vaut filename", async () => {
    const docZ = makeDoc({ id: "z", filename: "Zebre.pdf" });
    const docA = makeDoc({ id: "a", filename: "Alpha.pdf" });
    vi.mocked(projectsService.listDocuments).mockResolvedValue(
      ok({ documents: [docZ, docA], total: 2 }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(result.current.sortedDocuments).toHaveLength(2));

    act(() => result.current.handleSort("filename"));

    await waitFor(() => {
      expect(result.current.sortedDocuments.map((d) => d.id)).toEqual(["a", "z"]);
    });
  });

  it("handleSort sur le même champ inverse la direction", async () => {
    vi.mocked(projectsService.listDocuments).mockResolvedValue(ok({ documents: [], total: 0 }));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(result.current.documents.isPending).toBe(false));

    expect(result.current.sortDirection).toBe("desc");
    act(() => result.current.handleSort("created_at"));
    expect(result.current.sortDirection).toBe("asc");
    act(() => result.current.handleSort("created_at"));
    expect(result.current.sortDirection).toBe("desc");
  });

  it("handleSort sur un champ différent repart en asc", async () => {
    vi.mocked(projectsService.listDocuments).mockResolvedValue(ok({ documents: [], total: 0 }));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(result.current.documents.isPending).toBe(false));

    act(() => result.current.handleSort("filename"));

    expect(result.current.sortField).toBe("filename");
    expect(result.current.sortDirection).toBe("asc");
  });

  it("compose le résumé documents/en-traitement/erreurs/taille", async () => {
    const ready = makeDoc({ id: "a", status: "ready", size: 1000 });
    const processing = makeDoc({ id: "b", status: "processing", size: 2000 });
    const error = makeDoc({ id: "c", status: "error", size: 3000 });
    vi.mocked(projectsService.listDocuments).mockResolvedValue(
      ok({ documents: [ready, processing, error], total: 3 }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });

    await waitFor(() => {
      expect(result.current.summary).toBe("3 documents — 1 en traitement — 1 erreur — 6 KB");
    });
  });

  it("le résumé est absent quand la liste de documents est vide", async () => {
    vi.mocked(projectsService.listDocuments).mockResolvedValue(ok({ documents: [], total: 0 }));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });

    await waitFor(() => expect(result.current.documents.isPending).toBe(false));
    expect(result.current.summary).toBeNull();
  });
});

describe("useWorkspaceDocuments — règles métier", () => {
  it("fusionne un upload en cours dans sortedDocuments quand aucun doc réel ne correspond encore", async () => {
    vi.mocked(projectsService.listDocuments).mockResolvedValue(ok({ documents: [], total: 0 }));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(result.current.documents.isPending).toBe(false));

    act(() => {
      useUploadStore.getState().addUpload("upload-1", "nouveau.pdf", null);
    });

    await waitFor(() => {
      expect(result.current.sortedDocuments.map((d) => d.filename)).toContain("nouveau.pdf");
    });
  });

  it("ne double pas un upload une fois son document réel présent (résolu et dédoublonné)", async () => {
    const real = makeDoc({ id: "doc-real-1", filename: "nouveau.pdf" });
    vi.mocked(projectsService.listDocuments).mockResolvedValue(
      ok({ documents: [real], total: 1 }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(result.current.sortedDocuments).toHaveLength(1));

    act(() => {
      useUploadStore.getState().addUpload("upload-1", "nouveau.pdf", null);
      useUploadStore.getState().setResolved("upload-1", "doc-real-1");
    });

    await waitFor(() => {
      expect(
        result.current.sortedDocuments.filter((d) => d.id === "doc-real-1"),
      ).toHaveLength(1);
    });
  });

  it("handleBatchDelete attend que toutes les suppressions se règlent avant de vider la sélection", async () => {
    let resolveDelete: (() => void) | undefined;
    vi.mocked(projectsService.deleteDocument).mockReturnValue(
      new Promise((resolve) => {
        resolveDelete = () => resolve(ok(undefined));
      }),
    );
    vi.mocked(projectsService.listDocuments).mockResolvedValue(ok({ documents: [], total: 0 }));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(result.current.documents.isPending).toBe(false));

    act(() => useSelectionStore.getState().toggle("doc-1"));
    act(() => result.current.handleBatchDelete());

    expect(useSelectionStore.getState().selectedIds.has("doc-1")).toBe(true);

    await act(async () => {
      resolveDelete?.();
    });

    await waitFor(() => {
      expect(useSelectionStore.getState().selectedIds.size).toBe(0);
    });
  });

  it("handleBatchMove vide la sélection immédiatement, sans attendre le règlement des mutations", async () => {
    vi.mocked(projectsService.moveDocument).mockReturnValue(new Promise(() => {}));
    vi.mocked(projectsService.listDocuments).mockResolvedValue(ok({ documents: [], total: 0 }));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(result.current.documents.isPending).toBe(false));

    act(() => useSelectionStore.getState().toggle("doc-1"));
    act(() => result.current.handleBatchMove("folder-1"));

    expect(useSelectionStore.getState().selectedIds.size).toBe(0);
  });

  it("retire du store d'upload une entrée résolue une fois le document réel présent dans le cache", async () => {
    const real = makeDoc({ id: "doc-real-1", filename: "nouveau.pdf" });
    vi.mocked(projectsService.listDocuments).mockResolvedValue(
      ok({ documents: [real], total: 1 }),
    );
    const { wrapper } = createQueryClientWrapper();
    renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(Object.keys(useUploadStore.getState().uploads)).toEqual([]));

    act(() => {
      useUploadStore.getState().addUpload("upload-1", "nouveau.pdf", null);
      useUploadStore.getState().setResolved("upload-1", "doc-real-1");
    });

    await waitFor(() => {
      expect(useUploadStore.getState().uploads["upload-1"]).toBeUndefined();
    });
  });
});

describe("useWorkspaceDocuments — cas limites", () => {
  it("vide la sélection au changement de dossier courant", async () => {
    vi.mocked(projectsService.listDocuments).mockResolvedValue(ok({ documents: [], total: 0 }));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(result.current.documents.isPending).toBe(false));

    act(() => useSelectionStore.getState().toggle("doc-1"));
    expect(useSelectionStore.getState().selectedIds.size).toBe(1);

    act(() => result.current.setCurrentFolderId("folder-1"));

    await waitFor(() => {
      expect(useSelectionStore.getState().selectedIds.size).toBe(0);
    });
  });

  it("aucun document ne matche la recherche → liste triée vide", async () => {
    vi.mocked(projectsService.listDocuments).mockResolvedValue(
      ok({ documents: [makeDoc({ id: "a", filename: "Zebre.pdf" })], total: 1 }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useWorkspaceDocuments("p-1"), { wrapper });
    await waitFor(() => expect(result.current.sortedDocuments).toHaveLength(1));

    act(() => result.current.setSearch("introuvable"));

    await waitFor(() => {
      expect(result.current.sortedDocuments).toEqual([]);
    });
  });
});
