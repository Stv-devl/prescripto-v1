import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/apiClient";
import { attempt, type Result } from "@/lib/result";
import type {
  Project,
  ProjectList,
  CreateProjectInput,
  UpdateProjectInput,
} from "../types/types";

/**
 * Fetches all projects for the current tenant.
 */
export function listProjects(): Promise<Result<ProjectList>> {
  return attempt(() => apiGet<ProjectList>("/projects"));
}

/**
 * Fetches a single project by ID.
 */
export function getProject(projectId: string): Promise<Result<Project>> {
  return attempt(() => apiGet<Project>(`/projects/${projectId}`));
}

/**
 * Creates a new project.
 */
export function createProject(
  data: CreateProjectInput,
): Promise<Result<Project>> {
  return attempt(() => apiPost<Project>("/projects", data));
}

/**
 * Updates a project's metadata.
 */
export function updateProject(
  projectId: string,
  data: Partial<UpdateProjectInput>,
): Promise<Result<Project>> {
  return attempt(() => apiPatch<Project>(`/projects/${projectId}`, data));
}

/**
 * Deletes a project by ID.
 */
export function deleteProject(projectId: string): Promise<Result<void>> {
  return attempt(() => apiDelete(`/projects/${projectId}`));
}
