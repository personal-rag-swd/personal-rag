import { useState } from "react"
import { FileTextIcon, Loader2Icon } from "lucide-react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Field,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { apiFetch } from "@/lib/api-client"

type NoteCreateDialogProps = {
  notebookId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function NoteCreateDialog({
  notebookId,
  open,
  onOpenChange,
}: NoteCreateDialogProps) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState("")
  const [content, setContent] = useState("")
  const [isSaving, setIsSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    e.stopPropagation()

    const trimmedTitle = title.trim()
    const trimmedContent = content.trim()

    if (!trimmedTitle) {
      toast.error("Title is required")
      return
    }
    if (!trimmedContent) {
      toast.error("Content is required")
      return
    }

    setIsSaving(true)

    try {
      await apiFetch(`/api/v1/notebooks/${notebookId}/notes`, {
        method: "POST",
        data: {
          title: trimmedTitle,
          content: trimmedContent,
        },
      })

      toast.success("Note saved", {
        description: `${trimmedTitle} was added as a source text.`,
      })

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["notebooks", notebookId, "documents"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["notebooks", notebookId, "reports"],
        }),
        queryClient.invalidateQueries({ queryKey: ["notebooks"] }),
      ])

      onOpenChange(false)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "The note could not be saved."
      toast.error("Failed to save note", {
        description: message,
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-2xl border-border bg-card select-none sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg font-bold">
            <FileTextIcon className="size-5 text-primary" />
            <span>Create New Note</span>
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            Type your notes below. It will be saved as a source in this notebook.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="py-2">
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="note-title">Title</FieldLabel>
              <Input
                id="note-title"
                name="title"
                placeholder="e.g. Project Ideas, Summaries..."
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={isSaving}
                required
              />
            </Field>

            <Field>
              <FieldLabel htmlFor="note-content">Content</FieldLabel>
              <Textarea
                id="note-content"
                name="content"
                placeholder="Write your note content here..."
                value={content}
                onChange={(e) => setContent(e.target.value)}
                disabled={isSaving}
                className="min-h-36 resize-y"
                required
              />
            </Field>

            <DialogFooter className="gap-2 pt-3 sm:gap-0">
              <Button
                type="button"
                variant="ghost"
                className="rounded-xl border-border/60 font-semibold hover:bg-muted"
                onClick={() => onOpenChange(false)}
                disabled={isSaving}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                className="rounded-xl bg-primary px-4 font-semibold text-primary-foreground shadow-xs hover:bg-primary/95"
                disabled={isSaving}
              >
                {isSaving ? (
                  <>
                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  "Save Note"
                )}
              </Button>
            </DialogFooter>
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  )
}
