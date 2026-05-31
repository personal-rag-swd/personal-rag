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
  createdAt: string;
  lastActiveAt: string;
  tags: string[];
};

export type NotebookDocument = {
  id: string;
  notebookId: string;
  filename: string;
  contentType: string | null;
  size: number | null;
  status: "pending" | "uploaded" | "processing" | "indexed" | "failed" | string;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
};

export type NotebookDocumentEvent =
  | {
      type: "snapshot";
      notebook_id: string;
      documents: NotebookDocumentApiPayload[];
      timestamp: string;
    }
  | {
      type: "document_update";
      notebook_id: string;
      document: NotebookDocumentApiPayload;
      timestamp: string;
    }
  | {
      type: "ping";
      notebook_id: string;
      timestamp: string;
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
  created_at: string;
  updated_at: string;
  last_active_at: string;
  tags: string[];
};

export type NotebookPopulateApiPayload = NotebookApiPayload & {
  document_count: number;
  query_count: number;
};

export type NotebookDocumentApiPayload = {
  id: string;
  notebook_id: string;
  filename: string;
  content_type: string | null;
  size: number | null;
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

// ─── Reports ────────────────────────────────────────────────────────────────

export type ReportType = "briefing" | "study_guide" | "blog" | "custom";

export type BriefingDocContent = {
  executive_summary: string;
  key_takeaways: string[];
  strategic_implications: string[];
};

export type StudyGuideContent = {
  glossary: { term: string; definition: string }[];
  quiz: {
    question: string;
    options: string[];
    answer: string;
    explanation: string;
  }[];
};

export type BlogPostContent = {
  title: string;
  hook: string;
  markdown_body: string;
};

export type CustomReportContent = {
  markdown_content: string;
};

export type ReportContent =
  | BriefingDocContent
  | StudyGuideContent
  | BlogPostContent
  | CustomReportContent;

export type NotebookReportApiPayload = {
  id: string;
  notebook_id: string;
  report_type: ReportType;
  content: ReportContent;
  created_at: string;
  updated_at: string;
};

export type NotebookReport = {
  id: string;
  notebookId: string;
  reportType: ReportType;
  content: ReportContent;
  createdAt: string;
  updatedAt: string;
};
