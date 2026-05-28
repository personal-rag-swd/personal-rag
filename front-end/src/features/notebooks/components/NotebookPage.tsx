import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { useNotebookQuery } from "@/features/notebooks/api";
import { cn } from "@/lib/utils";

import { ChatPanel } from "./notebook-page/ChatPanel";
import { NotebookHeader } from "./notebook-page/NotebookHeader";
import { NotebookError, NotebookSkeleton } from "./notebook-page/NotebookStates";
import { SourcesPanel } from "./notebook-page/SourcesPanel";
import { StudioPanel } from "./notebook-page/StudioPanel";
import { UpdateNotebookDialog } from "./UpdateNotebookDialog";
import { DeleteNotebookDialog } from "./DeleteNotebookDialog";

type TabType = "sources" | "chat" | "studio";

export function NotebookPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: notebook, isLoading, isError, error } = useNotebookQuery(id);
  const [activeTab, setActiveTab] = useState<TabType>("chat");
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
  const [isRightCollapsed, setIsRightCollapsed] = useState(false);

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
    <div className="flex flex-col h-full animate-in fade-in duration-300">
      <NotebookHeader
        name={notebook.name}
        tags={notebook.tags}
        documentCount={notebook.documentCount}
        queryCount={notebook.queryCount}
        onEditClick={() => setIsEditOpen(true)}
        onDeleteClick={() => setIsDeleteOpen(true)}
      />

      {/* Mobile/Tablet Tabs Navigation */}
      <div className="flex lg:hidden border-b border-border/40 bg-background/95 backdrop-blur-xs justify-center shrink-0">
        <div className="flex w-full max-w-md justify-around px-2">
          {(["sources", "chat", "studio"] as const).map((tab) => {
            const label = tab.charAt(0).toUpperCase() + tab.slice(1);
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={cn(
                  "relative py-3.5 px-4 text-xs sm:text-sm font-medium transition-all duration-200 focus-visible:outline-none select-none",
                  isActive
                    ? "text-foreground font-semibold"
                    : "text-muted-foreground hover:text-foreground/80"
                )}
              >
                {label}
                {isActive && (
                  <span className="absolute bottom-0 left-2 right-2 h-0.5 bg-primary rounded-full animate-in slide-in-from-bottom-1 duration-200" />
                )}
              </button>
            );
          })}
        </div>
      </div>

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
    </div>
  );
}

