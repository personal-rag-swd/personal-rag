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

import { ChatPanel } from "./notebook-page/ChatPanel";
import { NotebookHeader } from "./notebook-page/NotebookHeader";
import { NotebookError, NotebookSkeleton } from "./notebook-page/NotebookStates";
import { ReportsPanel } from "./notebook-page/ReportsPanel";
import { SourcesPanel } from "./notebook-page/SourcesPanel";
import { StudioPanel } from "./notebook-page/StudioPanel";
import { UpdateNotebookDialog } from "./UpdateNotebookDialog";
import { DeleteNotebookDialog } from "./DeleteNotebookDialog";
import { cn } from "@/lib/utils";

type TabType = "sources" | "chat" | "studio";
type StudioFeature = "reports";

export function NotebookPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: notebook, isLoading, isError, error } = useNotebookQuery(id);
  const [activeTab, setActiveTab] = useState<TabType>("chat");
  const [activeStudioFeature, setActiveStudioFeature] = useState<StudioFeature | null>(null);
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
  const [isRightCollapsed, setIsRightCollapsed] = useState(false);

  const handleStudioActionActivate = (actionId: string) => {
    if (actionId === "reports") {
      setActiveStudioFeature("reports");
    }
  };

  // Modal dialog states
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

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
          className="h-full lg:hidden"
        >
          <div className="flex w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="sources">Sources</TabsTrigger>
              <TabsTrigger value="chat">Chat</TabsTrigger>
              <TabsTrigger value="studio">Studio</TabsTrigger>
            </TabsList>
          </div>
          <TabsContent value="sources" className="min-h-0">
            <PanelCard title="Sources">
              <SourcesPanel notebookId={id} />
            </PanelCard>
          </TabsContent>
          <TabsContent value="chat" className="min-h-0">
            <PanelCard title="Chat">
              <ChatPanel notebookId={id} />
            </PanelCard>
          </TabsContent>
          <TabsContent value="studio" className="min-h-0">
            <PanelCard title="Studio">
              <StudioPanel />
            </PanelCard>
          </TabsContent>
        </Tabs>

      <div className="flex flex-1 overflow-hidden">
        <div className={cn(
          "w-full h-full lg:shrink-0 overflow-hidden transition-all duration-300 ease-in-out",
          isLeftCollapsed ? "lg:w-14" : "lg:w-1/4",
          activeTab === "sources" ? "block" : "hidden lg:block"
        )}>
          <SourcesPanel
            notebookId={id}
            isCollapsed={isLeftCollapsed}
            onToggleCollapse={() => setIsLeftCollapsed(!isLeftCollapsed)}
          />
        </div>

        <div className={cn(
          "w-full h-full lg:flex-1 lg:min-w-0 overflow-hidden",
          activeTab === "chat" ? "block" : "hidden lg:block"
        )}>
          <ChatPanel notebookId={id} />
        </div>

        <div className={cn(
          "w-full h-full lg:shrink-0 overflow-hidden transition-all duration-300 ease-in-out",
          isRightCollapsed ? "lg:w-14" : "lg:w-1/4",
          activeTab === "studio" ? "block" : "hidden lg:block"
        )}>
          <StudioPanel
            isCollapsed={isRightCollapsed}
            onToggleCollapse={() => setIsRightCollapsed(!isRightCollapsed)}
            onActivate={handleStudioActionActivate}
            activeFeature={activeStudioFeature}
          />
        </div>
      </div>

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

      <ReportsPanel
        notebookId={id}
        open={activeStudioFeature === "reports"}
        onOpenChange={(open) => setActiveStudioFeature(open ? "reports" : null)}
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
