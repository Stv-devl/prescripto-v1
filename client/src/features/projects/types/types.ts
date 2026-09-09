import { z } from "zod/v4";

// --- Project ---

export interface Project {
  id: string;
  tenant_id: string;
  name: string;
  phase: string;
  status: string;
  address: string;
  client: string;
  architect: string;
  architect_address: string;
  bureau_thermique: string;
  bureau_thermique_address: string;
  bureau_vrd: string;
  bureau_vrd_address: string;
  bureau_beton: string;
  bureau_beton_address: string;
  economiste: string;
  economiste_address: string;
  controleur_technique: string;
  controleur_technique_address: string;
  is_favorite: boolean;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectList {
  projects: Project[];
  total: number;
}

export const createProjectSchema = z.object({
  name: z.string().min(1, "Le nom est requis").max(255),
  phase: z.string().max(50),
});

export type CreateProjectInput = z.infer<typeof createProjectSchema>;

export const updateProjectSchema = z.object({
  name: z.string().min(1, "Le nom est requis").max(255),
  phase: z.string().max(50).optional(),
  status: z.string().max(50),
  address: z.string().max(500),
  client: z.string().max(255),
  architect: z.string().max(255),
  architect_address: z.string().max(500),
  bureau_thermique: z.string().max(255),
  bureau_thermique_address: z.string().max(500),
  bureau_vrd: z.string().max(255),
  bureau_vrd_address: z.string().max(500),
  bureau_beton: z.string().max(255),
  bureau_beton_address: z.string().max(500),
  economiste: z.string().max(255),
  economiste_address: z.string().max(500),
  controleur_technique: z.string().max(255),
  controleur_technique_address: z.string().max(500),
  is_favorite: z.boolean().optional(),
});

export type UpdateProjectInput = z.infer<typeof updateProjectSchema>;

// --- Document ---

export type DocumentStatus = "uploading" | "processing" | "ready" | "error";

export interface Document {
  id: string;
  project_id: string;
  folder_id: string | null;
  filename: string;
  type: string;
  lot: string;
  phase: string;
  size: number;
  status: DocumentStatus;
  created_at: string;
  updated_at: string;
}

export interface DocumentList {
  documents: Document[];
  total: number;
}

// --- Folder ---

export interface Folder {
  id: string;
  project_id: string;
  name: string;
  lot: string;
  phase: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface FolderList {
  folders: Folder[];
  total: number;
}

export const createFolderSchema = z.object({
  name: z.string().min(1, "Le nom est requis").max(255),
  lot: z.string().max(100),
  phase: z.string().max(50),
});

export type CreateFolderInput = z.infer<typeof createFolderSchema>;
