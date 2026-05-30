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
import { useIsDesktop } from "@/hooks/use-media-query";
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
  const isDesktop = useIsDesktop();
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

      <div className="flex min-h-0 flex-1 flex-col p-2">
        {isDesktop ? (
          /* Desktop: three side-by-side, collapsible columns */
          <div className="flex min-h-0 flex-1 gap-2 overflow-hidden">
            <div
              className={cn(
                "h-full shrink-0 overflow-hidden rounded-xl border transition-all duration-300 ease-in-out",
                isLeftCollapsed ? "w-14" : "w-1/4"
              )}
            >
              <SourcesPanel
                notebookId={id}
                isCollapsed={isLeftCollapsed}
                onToggleCollapse={() => setIsLeftCollapsed(!isLeftCollapsed)}
              />
            </div>

            <div className="h-full min-w-0 flex-1 overflow-hidden rounded-xl border">
              <ChatPanel notebookId={id} />
            </div>

            <div
              className={cn(
                "h-full shrink-0 overflow-hidden rounded-xl border transition-all duration-300 ease-in-out",
                isRightCollapsed ? "w-14" : "w-1/4"
              )}
            >
              <StudioPanel
                isCollapsed={isRightCollapsed}
                onToggleCollapse={() => setIsRightCollapsed(!isRightCollapsed)}
                onActivate={handleStudioActionActivate}
                activeFeature={activeStudioFeature}
              />
            </div>
          </div>
        ) : (
          /* Mobile / tablet: one panel at a time via tabs */
          <Tabs
            value={activeTab}
            onValueChange={(value) => setActiveTab(value as TabType)}
            className="flex min-h-0 flex-1 flex-col gap-2"
          >
            <TabsList className="grid w-full shrink-0 grid-cols-3">
              <TabsTrigger value="sources">Sources</TabsTrigger>
              <TabsTrigger value="chat">Chat</TabsTrigger>
              <TabsTrigger value="studio">Studio</TabsTrigger>
            </TabsList>
            <TabsContent value="sources" className="mt-0 min-h-0 flex-1">
              <PanelCard title="Sources">
                <SourcesPanel notebookId={id} />
              </PanelCard>
            </TabsContent>
            <TabsContent value="chat" className="mt-0 min-h-0 flex-1">
              <PanelCard title="Chat">
                <ChatPanel notebookId={id} />
              </PanelCard>
            </TabsContent>
            <TabsContent value="studio" className="mt-0 min-h-0 flex-1">
              <PanelCard title="Studio">
                <StudioPanel />
              </PanelCard>
            </TabsContent>
          </Tabs>
        )}
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
