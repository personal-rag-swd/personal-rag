import * as React from "react";
import { AlertTriangleIcon, Loader2Icon } from "lucide-react";

import { useDeleteNotebookMutation } from "@/features/notebooks/api";
import { type Notebook } from "@/features/notebooks/types";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type DeleteNotebookDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  notebook: Notebook;
  onSuccess: () => void;
  onClose: () => void;
};

export function DeleteNotebookDialog({
  open,
  onOpenChange,
  notebook,
  onSuccess,
  onClose,
}: DeleteNotebookDialogProps) {
  const deleteMutation = useDeleteNotebookMutation();
  const [error, setError] = React.useState("");

  const handleDelete = async () => {
    setError("");
    try {
      await deleteMutation.mutateAsync(notebook.id);
      onSuccess();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete notebook."
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md select-none rounded-2xl border-border bg-card">
        <DialogHeader className="flex flex-col items-center text-center">
          <div className="flex size-12 items-center justify-center rounded-full bg-destructive/15 text-destructive mb-3">
            <AlertTriangleIcon className="size-6" />
          </div>
          <DialogTitle className="text-lg font-bold text-foreground">
            Delete Workspace Notebook?
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground max-w-xs mt-1">
            This will permanently delete the workspace <strong className="font-semibold text-foreground">"{notebook.name}"</strong>, including all uploaded documents, processed chunks, and chat history. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-lg p-2.5 text-center my-1">
            {error}
          </div>
        )}

        <DialogFooter className="flex-col sm:flex-row gap-2 pt-2 mt-2 w-full justify-stretch">
          <Button
            type="button"
            variant="ghost"
            className="flex-1 rounded-xl font-semibold border border-border/60 hover:bg-muted"
            onClick={onClose}
            disabled={deleteMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            className="flex-1 rounded-xl font-semibold px-4 shadow-sm"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? (
              <>
                <Loader2Icon className="mr-1.5 size-4 animate-spin" />
                Deleting...
              </>
            ) : (
              "Delete Workspace"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
