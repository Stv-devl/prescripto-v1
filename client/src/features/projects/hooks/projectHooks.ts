import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { unwrap } from "@/lib/result";
import {
  listProjects,
  getProject,
  createProject,
  updateProject,
  deleteProject,
} from "../services/projects.service";
import type { CreateProjectInput, UpdateProjectInput } from "../types/types";

/**
 * Fetches all projects.
 */
export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: async () => unwrap(await listProjects()),
  });
}

/**
 * Fetches a single project by ID.
 */
export function useProject(projectId: string) {
  return useQuery({
    queryKey: ["projects", projectId],
    queryFn: async () => unwrap(await getProject(projectId)),
    enabled: !!projectId,
  });
}

/**
 * Creates a project and invalidates the projects list.
 */
export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateProjectInput) =>
      unwrap(await createProject(data)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

/**
 * Updates a project's metadata and invalidates the project cache.
 */
export function useUpdateProject(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: UpdateProjectInput) =>
      unwrap(await updateProject(projectId, data)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

/**
 * Deletes a project and invalidates the projects list.
 */
export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (projectId: string) =>
      unwrap(await deleteProject(projectId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

/**
 * Toggles a project's favorite status via PATCH.
 */
export function useToggleFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      projectId,
      isFavorite,
    }: {
      projectId: string;
      isFavorite: boolean;
    }) =>
      unwrap(
        await updateProject(projectId, {
          is_favorite: !isFavorite,
        }),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

/**
 * Archives or unarchives a project via PATCH.
 */
export function useArchiveProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      projectId,
      currentStatus,
    }: {
      projectId: string;
      currentStatus: string;
    }) =>
      unwrap(
        await updateProject(projectId, {
          status: currentStatus === "archived" ? "active" : "archived",
        }),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}
