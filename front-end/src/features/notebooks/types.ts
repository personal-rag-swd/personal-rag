import { z } from "zod"

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
})

export type NotebookValues = z.input<typeof notebookSchema>

export type Notebook = {
  id: string
  name: string
  description: string
  createdAt: string
  lastActiveAt: string
  tags: string[]
}

export type NotebookDocument = {
  id: string
  notebookId: string
  filename: string
  contentType: string | null
  size: number | null
  status: "pending" | "uploaded" | "processing" | "indexed" | "failed" | string
  errorMessage: string | null
  createdAt: string
  updatedAt: string
}

export type NotebookDocumentEvent =
  | {
      type: "snapshot"
      notebook_id: string
      documents: NotebookDocumentApiPayload[]
      timestamp: string
    }
  | {
      type: "document_update"
      notebook_id: string
      document: NotebookDocumentApiPayload
      timestamp: string
    }
  | {
      type: "ping"
      notebook_id: string
      timestamp: string
    }

export type NotebookActionState = {
  values?: Partial<NotebookValues>
  notebook?: Notebook
  formError?: string
  fieldErrors?: Partial<Record<"name" | "description" | "tags", string>>
}

export type NotebookApiPayload = {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
  last_active_at: string
  tags: string[]
}

export type NotebookPopulateApiPayload = NotebookApiPayload & {
  document_count: number
  query_count: number
}

export type NotebookDocumentApiPayload = {
  id: string
  notebook_id: string
  filename: string
  content_type: string | null
  size: number | null
  status: string
  error_message: string | null
  created_at: string
  updated_at: string
}

// ─── Reports ────────────────────────────────────────────────────────────────

export type ReportType =
  | "briefing"
  | "study_guide"
  | "blog"
  | "custom"
  | "mindmap"

export type BriefingDocContent = {
  executive_summary: string
  key_takeaways: string[]
  strategic_implications: string[]
}

export type StudyGuideContent = {
  glossary: { term: string; definition: string }[]
  quiz: {
    question: string
    options: string[]
    answer: string
    explanation: string
  }[]
}

export type BlogPostContent = {
  title: string
  hook: string
  markdown_body: string
}

export type CustomReportContent = {
  markdown_content: string
}

export type MindMapNode = {
  id: string
  label: string
  type: "root" | "main" | "sub"
  parentId?: string | null
  description?: string | null
}

export type MindMapNodeApiPayload = Omit<MindMapNode, "parentId"> & {
  parent_id?: string | null
  parentId?: string | null
}

export type MindMapRelationship = {
  source: string
  target: string
  label: string
}

export type MindMapContent = {
  central_topic: string
  nodes: MindMapNode[]
  relationships?: MindMapRelationship[]
}

export type MindMapContentApiPayload = Omit<MindMapContent, "nodes"> & {
  nodes: MindMapNodeApiPayload[]
}

export type ReportContent =
  | BriefingDocContent
  | StudyGuideContent
  | BlogPostContent
  | CustomReportContent
  | MindMapContent

export type ReportContentApiPayload =
  | BriefingDocContent
  | StudyGuideContent
  | BlogPostContent
  | CustomReportContent
  | MindMapContentApiPayload

export type NotebookReportApiPayload =
  | {
      id: string
      notebook_id: string
      report_type: "briefing"
      content: BriefingDocContent
      created_at: string
      updated_at: string
    }
  | {
      id: string
      notebook_id: string
      report_type: "study_guide"
      content: StudyGuideContent
      created_at: string
      updated_at: string
    }
  | {
      id: string
      notebook_id: string
      report_type: "blog"
      content: BlogPostContent
      created_at: string
      updated_at: string
    }
  | {
      id: string
      notebook_id: string
      report_type: "custom"
      content: CustomReportContent
      created_at: string
      updated_at: string
    }
  | {
      id: string
      notebook_id: string
      report_type: "mindmap"
      content: MindMapContentApiPayload
      created_at: string
      updated_at: string
    }

export type NotebookReport =
  | {
      id: string
      notebookId: string
      reportType: "briefing"
      content: BriefingDocContent
      createdAt: string
      updatedAt: string
    }
  | {
      id: string
      notebookId: string
      reportType: "study_guide"
      content: StudyGuideContent
      createdAt: string
      updatedAt: string
    }
  | {
      id: string
      notebookId: string
      reportType: "blog"
      content: BlogPostContent
      createdAt: string
      updatedAt: string
    }
  | {
      id: string
      notebookId: string
      reportType: "custom"
      content: CustomReportContent
      createdAt: string
      updatedAt: string
    }
  | {
      id: string
      notebookId: string
      reportType: "mindmap"
      content: MindMapContent
      createdAt: string
      updatedAt: string
    }
