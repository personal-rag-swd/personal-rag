import * as React from "react"
import { AlertTriangleIcon, Loader2Icon } from "lucide-react"

import { useDeleteNotebookMutation } from "@/features/notebooks/api"
import { type Notebook } from "@/features/notebooks/types"
import { getErrorMessage } from "@/lib/utils"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

type DeleteNotebookDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  notebook: Notebook
  onSuccess: () => void
  onClose: () => void
}

export function DeleteNotebookDialog({
  open,
  onOpenChange,
  notebook,
  onSuccess,
  onClose,
}: DeleteNotebookDialogProps) {
  const deleteMutation = useDeleteNotebookMutation()
  const [error, setError] = React.useState("")

  const handleDelete = async () => {
    setError("")
    try {
      await deleteMutation.mutateAsync(notebook.id)
      onSuccess()
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete notebook."))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-2xl border-border bg-card select-none sm:max-w-md">
        <DialogHeader className="flex flex-col items-center text-center">
          <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-destructive/15 text-destructive">
            <AlertTriangleIcon className="size-6" />
          </div>
          <DialogTitle className="text-lg font-bold text-foreground">
            Delete Workspace Notebook?
          </DialogTitle>
          <DialogDescription className="mt-1 max-w-xs text-xs text-muted-foreground">
            This will permanently delete the workspace{" "}
            <strong className="font-semibold text-foreground">
              "{notebook.name}"
            </strong>
            , including all uploaded documents, processed chunks, and chat
            history. This action cannot be undone.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="my-1 rounded-lg border border-destructive/20 bg-destructive/10 p-2.5 text-center text-xs text-destructive">
            {error}
          </div>
        )}

        <DialogFooter className="mt-2 w-full flex-col justify-stretch gap-2 pt-2 sm:flex-row">
          <Button
            type="button"
            variant="ghost"
            className="flex-1 rounded-xl border border-border/60 font-semibold hover:bg-muted"
            onClick={onClose}
            disabled={deleteMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            className="flex-1 rounded-xl px-4 font-semibold shadow-sm"
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
  )
}
