import * as React from "react"
import { Loader2Icon, Trash2Icon } from "lucide-react"
import { toast } from "sonner"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useClearNotebookChatMutation } from "@/features/notebooks/api"

type ClearChatButtonProps = {
  notebookId: string
  /** Called after the chat history is successfully cleared. */
  onCleared: () => void
}

export function ClearChatButton({
  notebookId,
  onCleared,
}: ClearChatButtonProps) {
  const [isOpen, setIsOpen] = React.useState(false)
  const clearChatMutation = useClearNotebookChatMutation(notebookId)

  const handleClear = async () => {
    try {
      await clearChatMutation.mutateAsync()
      setIsOpen(false)
      onCleared()
      toast.success("Chat cleared")
    } catch {
      toast.error("Couldn't clear the chat. Please try again.")
    }
  }

  return (
    <AlertDialog open={isOpen} onOpenChange={setIsOpen}>
      <Tooltip>
        <TooltipTrigger
          render={
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className="text-muted-foreground hover:text-destructive"
              onClick={() => setIsOpen(true)}
              aria-label="Clear chat"
            />
          }
        >
          <Trash2Icon />
        </TooltipTrigger>
        <TooltipContent side="bottom">Clear chat</TooltipContent>
      </Tooltip>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Clear chat?</AlertDialogTitle>
          <AlertDialogDescription>
            This permanently deletes every message in this notebook's chat. Your
            sources and reports are not affected. This action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={clearChatMutation.isPending}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={clearChatMutation.isPending}
            onClick={(event) => {
              event.preventDefault()
              void handleClear()
            }}
          >
            {clearChatMutation.isPending ? (
              <Loader2Icon data-icon="inline-start" className="animate-spin" />
            ) : (
              <Trash2Icon data-icon="inline-start" />
            )}
            Clear chat
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
