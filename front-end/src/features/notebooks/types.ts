import { z } from "zod";

export const notebookSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Notebook name is required.")
    .max(120, "Notebook name must be 120 characters or fewer."),
  description: z
    .string()
    .trim()
    .max(1000, "Description must be 1000 characters or fewer."),
  tags: z.string().trim(),
});

export type NotebookValues = z.input<typeof notebookSchema>;

export type Notebook = {
  id: string;
  name: string;
  description: string;
  documentCount: number;
  queryCount: number;
  createdAt: string;
  lastActiveAt: string;
  tags: string[];
};

export type NotebookActionState = {
  values?: Partial<NotebookValues>;
  notebook?: Notebook;
  formError?: string;
  fieldErrors?: Partial<Record<"name" | "description" | "tags", string>>;
};

export type NotebookApiPayload = {
  id: string;
  name: string;
  description: string;
  document_count: number;
  query_count: number;
  created_at: string;
  updated_at: string;
  last_active_at: string;
  tags: string[];
};
