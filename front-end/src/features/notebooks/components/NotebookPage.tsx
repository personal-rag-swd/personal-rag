import { useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  useNotebookQuery,
  useGenerateNotebookReportMutation,
} from "@/features/notebooks/api"
import type { NotebookReport } from "@/features/notebooks/types"

import { ChatPanel } from "./notebook-page/ChatPanel"
import { NotebookHeader } from "./notebook-page/NotebookHeader"
import { NotebookError, NotebookSkeleton } from "./notebook-page/NotebookStates"
import { SourcesPanel } from "./notebook-page/SourcesPanel"
import { StudioPanel } from "./notebook-page/StudioPanel"
import { ReportsPanel } from "./notebook-page/ReportsPanel"
import { MindMapDialog } from "./notebook-page/MindMapDialog"
import { ReportGenerateDialog } from "./notebook-page/ReportGenerateDialog"
import { MindMapGenerateDialog } from "./notebook-page/MindMapGenerateDialog"
import {
  QuizGenerateDialog,
  type QuizQuestionCount,
  type QuizDifficulty,
} from "./notebook-page/QuizGenerateDialog"
import { QuizDialog } from "./notebook-page/QuizDialog"
import {
  FlashcardsGenerateDialog,
  type FlashcardCount,
  type FlashcardDifficulty,
} from "./notebook-page/FlashcardsGenerateDialog"
import { FlashcardsDialog } from "./notebook-page/FlashcardsDialog"
import { UpdateNotebookDialog } from "./UpdateNotebookDialog"
import { DeleteNotebookDialog } from "./DeleteNotebookDialog"

type TabType = "sources" | "chat" | "studio"

export function NotebookPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data: notebook, isLoading, isError, error } = useNotebookQuery(id)
  const [activeTab, setActiveTab] = useState<TabType>("chat")

  // Modal dialog states
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [isReportGenerateOpen, setIsReportGenerateOpen] = useState(false)
  const [isReportViewerOpen, setIsReportViewerOpen] = useState(false)
  const [isMindMapGenerateOpen, setIsMindMapGenerateOpen] = useState(false)
  const [isMindMapViewerOpen, setIsMindMapViewerOpen] = useState(false)
  const [selectedReport, setSelectedReport] = useState<NotebookReport | null>(
    null
  )
  const [selectedMindMap, setSelectedMindMap] = useState<NotebookReport | null>(
    null
  )
  const [isQuizGenerateOpen, setIsQuizGenerateOpen] = useState(false)
  const [isQuizViewerOpen, setIsQuizViewerOpen] = useState(false)
  const [selectedQuiz, setSelectedQuiz] = useState<NotebookReport | null>(null)
  const [isFlashcardsGenerateOpen, setIsFlashcardsGenerateOpen] =
    useState(false)
  const [isFlashcardsViewerOpen, setIsFlashcardsViewerOpen] = useState(false)
  const [selectedFlashcards, setSelectedFlashcards] =
    useState<NotebookReport | null>(null)

  const handleViewReport = (report: NotebookReport) => {
    if (report.reportType === "mindmap") {
      setSelectedMindMap(report)
      setIsMindMapViewerOpen(true)
    } else if (report.reportType === "quiz") {
      setSelectedQuiz(report)
      setIsQuizViewerOpen(true)
    } else if (report.reportType === "flashcards") {
      setSelectedFlashcards(report)
      setIsFlashcardsViewerOpen(true)
    } else {
      setSelectedReport(report)
      setIsReportViewerOpen(true)
    }
  }

  const generateMindMapMutation = useGenerateNotebookReportMutation(id || "")

  const handleGenerateMindMap = async (
    detailLevel: "simple" | "intermediate" | "detailed",
    instructions: string
  ) => {
    setIsMindMapGenerateOpen(false)
    try {
      const data = await generateMindMapMutation.mutateAsync({
        reportType: "mindmap",
        additionalInstructions: instructions.trim() || undefined,
        detailLevel,
      })
      setSelectedMindMap(data)
      toast.success("Mind map generated successfully!")
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error"
      toast.error(`Failed to generate mind map: ${errorMessage}`)
    }
  }

  const generateQuizMutation = useGenerateNotebookReportMutation(id || "")

  const handleGenerateQuiz = async (
    numberOfQuestions: QuizQuestionCount,
    difficulty: QuizDifficulty,
    instructions: string
  ) => {
    setIsQuizGenerateOpen(false)
    try {
      await generateQuizMutation.mutateAsync({
        reportType: "quiz",
        numberOfQuestions,
        detailLevel: difficulty,
        additionalInstructions: instructions.trim() || undefined,
      })
      toast.success("Quiz is generating — it'll appear in Studio shortly.")
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error"
      toast.error(`Failed to start quiz: ${errorMessage}`)
    }
  }

  const generateFlashcardsMutation = useGenerateNotebookReportMutation(id || "")

  const handleGenerateFlashcards = async (
    numberOfCards: FlashcardCount,
    difficulty: FlashcardDifficulty,
    instructions: string
  ) => {
    setIsFlashcardsGenerateOpen(false)
    try {
      await generateFlashcardsMutation.mutateAsync({
        reportType: "flashcards",
        numberOfCards,
        detailLevel: difficulty,
        additionalInstructions: instructions.trim() || undefined,
      })
      toast.success("Flashcards are generating — they'll appear in Studio shortly.")
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error"
      toast.error(`Failed to start flashcards: ${errorMessage}`)
    }
  }

  if (!id) {
    return (
      <NotebookError message="This notebook could not be loaded. It may have been deleted or you don't have access." />
    )
  }

  if (isLoading) {
    return <NotebookSkeleton />
  }

  if (isError || !notebook) {
    return (
      <NotebookError
        message={
          error instanceof Error
            ? error.message
            : "This notebook could not be loaded. It may have been deleted or you don't have access."
        }
      />
    )
  }

  return (
    <div className="flex h-full min-h-0 animate-in flex-col bg-muted/30 duration-300 fade-in">
      <NotebookHeader
        name={notebook.name}
        tags={notebook.tags}
        onEditClick={() => setIsEditOpen(true)}
        onDeleteClick={() => setIsDeleteOpen(true)}
      />

      <div className="min-h-0 flex-1 p-2">
        <Tabs
          value={activeTab}
          onValueChange={(value) => setActiveTab(value as TabType)}
          className="flex h-full flex-col lg:hidden"
        >
          <div className="flex w-full shrink-0">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="sources">Sources</TabsTrigger>
              <TabsTrigger value="chat">Chat</TabsTrigger>
              <TabsTrigger value="studio">Studio</TabsTrigger>
            </TabsList>
          </div>
          <TabsContent value="sources" className="min-h-0 flex-1">
            <PanelCard title="Sources" hideHeaderBorder>
              <SourcesPanel notebookId={id} />
            </PanelCard>
          </TabsContent>
          <TabsContent value="chat" className="min-h-0 flex-1">
            <PanelCard title="Chat" hideHeaderBorder>
              <ChatPanel notebookId={id} />
            </PanelCard>
          </TabsContent>
          <TabsContent value="studio" className="min-h-0 flex-1">
            <PanelCard title="Studio" hideHeaderBorder>
              <StudioPanel
                notebookId={id}
                onActivate={(actionId) => {
                  if (actionId === "reports") {
                    setSelectedReport(null)
                    setIsReportGenerateOpen(true)
                  } else if (actionId === "mind-map") {
                    setSelectedMindMap(null)
                    setIsMindMapGenerateOpen(true)
                  } else if (actionId === "quiz") {
                    setIsQuizGenerateOpen(true)
                  } else if (actionId === "flashcards") {
                    setIsFlashcardsGenerateOpen(true)
                  }
                }}
                onViewReport={handleViewReport}
                isMindMapGenerating={generateMindMapMutation.isPending}
              />
            </PanelCard>
          </TabsContent>
        </Tabs>

        <div className="hidden h-full grid-cols-[minmax(0,1fr)_minmax(0,2fr)_minmax(0,1fr)] gap-2 lg:grid">
          <PanelCard title="Sources" hideHeaderBorder>
            <SourcesPanel notebookId={id} />
          </PanelCard>
          <PanelCard title="Chat">
            <ChatPanel notebookId={id} />
          </PanelCard>
          <PanelCard title="Studio" hideHeaderBorder>
            <StudioPanel
              notebookId={id}
              onActivate={(actionId) => {
                if (actionId === "reports") {
                  setSelectedReport(null)
                  setIsReportGenerateOpen(true)
                } else if (actionId === "mind-map") {
                  setSelectedMindMap(null)
                  setIsMindMapGenerateOpen(true)
                } else if (actionId === "quiz") {
                  setIsQuizGenerateOpen(true)
                } else if (actionId === "flashcards") {
                  setIsFlashcardsGenerateOpen(true)
                }
              }}
              onViewReport={handleViewReport}
              isMindMapGenerating={generateMindMapMutation.isPending}
            />
          </PanelCard>
        </div>
      </div>

      <ReportGenerateDialog
        notebookId={id}
        open={isReportGenerateOpen}
        onOpenChange={setIsReportGenerateOpen}
        onGenerated={(report) => setSelectedReport(report)}
      />

      <ReportsPanel
        open={isReportViewerOpen}
        onOpenChange={(open) => {
          setIsReportViewerOpen(open)
          if (!open) setSelectedReport(null)
        }}
        report={selectedReport}
      />

      <MindMapGenerateDialog
        open={isMindMapGenerateOpen}
        onOpenChange={setIsMindMapGenerateOpen}
        isGenerating={generateMindMapMutation.isPending}
        onGenerate={handleGenerateMindMap}
      />

      <MindMapDialog
        key={
          isMindMapViewerOpen
            ? `open-${selectedMindMap?.id ?? "latest"}`
            : "closed"
        }
        notebookId={id}
        notebookName={notebook.name}
        open={isMindMapViewerOpen}
        onOpenChange={(open) => {
          setIsMindMapViewerOpen(open)
          if (!open) setSelectedMindMap(null)
        }}
        initialMap={selectedMindMap}
      />

      <QuizGenerateDialog
        open={isQuizGenerateOpen}
        onOpenChange={setIsQuizGenerateOpen}
        isGenerating={generateQuizMutation.isPending}
        onGenerate={handleGenerateQuiz}
      />

      <QuizDialog
        key={
          isQuizViewerOpen ? `quiz-${selectedQuiz?.id ?? "none"}` : "quiz-closed"
        }
        open={isQuizViewerOpen}
        onOpenChange={(open) => {
          setIsQuizViewerOpen(open)
          if (!open) setSelectedQuiz(null)
        }}
        report={selectedQuiz}
      />

      <FlashcardsGenerateDialog
        open={isFlashcardsGenerateOpen}
        onOpenChange={setIsFlashcardsGenerateOpen}
        isGenerating={generateFlashcardsMutation.isPending}
        onGenerate={handleGenerateFlashcards}
      />

      <FlashcardsDialog
        key={
          isFlashcardsViewerOpen
            ? `flashcards-${selectedFlashcards?.id ?? "none"}`
            : "flashcards-closed"
        }
        open={isFlashcardsViewerOpen}
        onOpenChange={(open) => {
          setIsFlashcardsViewerOpen(open)
          if (!open) setSelectedFlashcards(null)
        }}
        report={selectedFlashcards}
      />

      {/* Edit & Delete Dialog Modals */}
      <UpdateNotebookDialog
        key={notebook.id}
        open={isEditOpen}
        onOpenChange={setIsEditOpen}
        notebook={notebook}
        onSuccess={(updated) => {
          toast.success("Notebook updated", {
            description: `"${updated.name}" was updated successfully.`,
          })
          setIsEditOpen(false)
        }}
        onClose={() => setIsEditOpen(false)}
      />

      <DeleteNotebookDialog
        open={isDeleteOpen}
        onOpenChange={setIsDeleteOpen}
        notebook={notebook}
        onSuccess={() => {
          toast.success("Notebook deleted", {
            description: `"${notebook.name}" was deleted successfully.`,
          })
          setIsDeleteOpen(false)
          void navigate("/dashboard")
        }}
        onClose={() => setIsDeleteOpen(false)}
      />
    </div>
  )
}

function PanelCard({
  title,
  children,
  hideHeaderBorder,
}: {
  title: string
  children: React.ReactNode
  hideHeaderBorder?: boolean
}) {
  return (
    <Card className="h-full min-h-0 gap-0 py-0">
      <CardHeader
        className={cn(
          "flex min-h-12 items-center py-0 pb-0!",
          !hideHeaderBorder && "border-b"
        )}
      >
        <CardTitle className="text-sm leading-none">{title}</CardTitle>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 px-0">{children}</CardContent>
    </Card>
  )
}
