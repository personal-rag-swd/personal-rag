import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useNotebookQuery } from "@/features/notebooks/api";
import type { NotebookReport } from "@/features/notebooks/types";

import { ChatPanel } from "./notebook-page/ChatPanel";
import { NotebookHeader } from "./notebook-page/NotebookHeader";
import { NotebookError, NotebookSkeleton } from "./notebook-page/NotebookStates";
import { SourcesPanel } from "./notebook-page/SourcesPanel";
import { StudioPanel } from "./notebook-page/StudioPanel";
import { ReportsPanel } from "./notebook-page/ReportsPanel";
import { MindMapDialog } from "./notebook-page/MindMapDialog";
import { UpdateNotebookDialog } from "./UpdateNotebookDialog";
import { DeleteNotebookDialog } from "./DeleteNotebookDialog";

type TabType = "sources" | "chat" | "studio";

export function NotebookPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: notebook, isLoading, isError, error } = useNotebookQuery(id);
  const [activeTab, setActiveTab] = useState<TabType>("chat");

  // Modal dialog states
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isReportsOpen, setIsReportsOpen] = useState(false);
  const [isMindMapOpen, setIsMindMapOpen] = useState(false);
  const [selectedReport, setSelectedReport] = useState<NotebookReport | null>(null);
  const [selectedMindMap, setSelectedMindMap] = useState<NotebookReport | null>(null);

  const handleViewReport = (report: NotebookReport) => {
    if (report.reportType === "mindmap") {
      setSelectedMindMap(report);
      setIsMindMapOpen(true);
    } else {
      setSelectedReport(report);
      setIsReportsOpen(true);
    }
  };

  if (!id) {
    return (
      <NotebookError message="This notebook could not be loaded. It may have been deleted or you don't have access." />
    );
  }

  if (isLoading) {
    return <NotebookSkeleton />;
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
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-muted/30 animate-in fade-in duration-300">
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
          <TabsContent value="sources" className="flex-1 min-h-0">
            <PanelCard title="Sources">
              <SourcesPanel notebookId={id} />
            </PanelCard>
          </TabsContent>
          <TabsContent value="chat" className="flex-1 min-h-0">
            <PanelCard title="Chat">
              <ChatPanel notebookId={id} />
            </PanelCard>
          </TabsContent>
          <TabsContent value="studio" className="flex-1 min-h-0">
            <PanelCard title="Studio">
              <StudioPanel
                notebookId={id}
                onActivate={(actionId) => {
                  if (actionId === "reports") {
                    setSelectedReport(null);
                    setIsReportsOpen(true);
                  } else if (actionId === "mind-map") {
                    setSelectedMindMap(null);
                    setIsMindMapOpen(true);
                  }
                }}
                onViewReport={handleViewReport}
              />
            </PanelCard>
          </TabsContent>
        </Tabs>

        <div className="hidden h-full grid-cols-[minmax(0,1fr)_minmax(0,2fr)_minmax(0,1fr)] gap-2 lg:grid">
          <PanelCard title="Sources">
            <SourcesPanel notebookId={id} />
          </PanelCard>
          <PanelCard title="Chat">
            <ChatPanel notebookId={id} />
          </PanelCard>
          <PanelCard title="Studio">
            <StudioPanel
              notebookId={id}
              onActivate={(actionId) => {
                if (actionId === "reports") {
                  setSelectedReport(null);
                  setIsReportsOpen(true);
                } else if (actionId === "mind-map") {
                  setSelectedMindMap(null);
                  setIsMindMapOpen(true);
                }
              }}
              onViewReport={handleViewReport}
            />
          </PanelCard>
        </div>
      </div>

      <ReportsPanel
        notebookId={id}
        open={isReportsOpen}
        onOpenChange={(open) => {
          setIsReportsOpen(open);
          if (!open) setSelectedReport(null);
        }}
        initialReport={selectedReport}
      />

      <MindMapDialog
        key={isMindMapOpen ? "open" : "closed"}
        notebookId={id}
        notebookName={notebook.name}
        open={isMindMapOpen}
        onOpenChange={(open) => {
          setIsMindMapOpen(open);
          if (!open) setSelectedMindMap(null);
        }}
        initialMap={selectedMindMap}
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
          });
          setIsEditOpen(false);
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
          });
          setIsDeleteOpen(false);
          void navigate("/dashboard");
        }}
        onClose={() => setIsDeleteOpen(false)}
      />
    </div>
  );
}

function PanelCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="h-full min-h-0 gap-0 py-0">
      <CardHeader className="flex min-h-12 items-center border-b py-0 !pb-0">
        <CardTitle className="text-sm leading-none">{title}</CardTitle>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 px-0">{children}</CardContent>
    </Card>
  );
}
