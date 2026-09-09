import { renderHook, waitFor } from "@testing-library/react";
import type { DragEvent } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { serviceError } from "@/lib/errors";
import { err, ok } from "@/lib/result";
import { createQueryClientWrapper } from "@/test/utils";
import * as projectsService from "../services/projects.service";
import type { Project } from "../types/types";
import * as dragUtils from "../utils/dragUtils";
import { useProjectsPageDrop } from "./useProjectsPageDrop";

const navigate = vi.fn();

vi.mock("../services/projects.service");
vi.mock("../utils/dragUtils", async (importOriginal) => ({
  ...(await importOriginal<typeof dragUtils>()),
  readDirectoryEntries: vi.fn(),
}));
vi.mock("react-router-dom", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
}));

function droppedFolder(): DragEvent {
  const entry = { isDirectory: true, name: "Villa Ada" };
  return {
    preventDefault: () => {},
    stopPropagation: () => {},
    dataTransfer: {
      items: [{ webkitGetAsEntry: () => entry }],
    },
  } as unknown as DragEvent;
}

describe("useProjectsPageDrop", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(dragUtils.readDirectoryEntries).mockResolvedValue([
      new File(["x"], "cctp.pdf", { type: "application/pdf" }),
    ]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not navigate when the project cannot be created", async () => {
    vi.mocked(projectsService.createProject).mockResolvedValue(
      err(serviceError("forbidden", "HTTP 403")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useProjectsPageDrop(), { wrapper });

    await result.current.onDrop(droppedFolder());

    await waitFor(() => {
      expect(result.current.isCreating).toBe(false);
    });
    expect(navigate).not.toHaveBeenCalled();
  });

  it("navigates to the project it created", async () => {
    vi.mocked(projectsService.createProject).mockResolvedValue(
      ok({ id: "p-7" } as Project),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useProjectsPageDrop(), { wrapper });

    await result.current.onDrop(droppedFolder());

    await waitFor(() => {
      expect(navigate).toHaveBeenCalledWith("/projects/p-7");
    });
  });
});
