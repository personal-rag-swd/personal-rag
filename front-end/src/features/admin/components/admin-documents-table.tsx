import * as React from "react"
import { toast } from "sonner"
import { EllipsisVerticalIcon } from "lucide-react"
import type { ColumnDef } from "@tanstack/react-table"

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
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  useAdminDocumentsQuery,
  useDeleteDocumentMutation,
  useUpdateDocumentMutation,
} from "../api"
import type { AdminDocument } from "../types"

// Lazy-loaded so the udoc-viewer WASM wrapper is only fetched when an admin
// actually opens a document preview.
const DocumentPreviewDialog = React.lazy(() =>
  import("./document-preview-dialog").then((module) => ({
    default: module.DocumentPreviewDialog,
  }))
)

const PAGE_SIZE = 20

const STATUSES = [
  "all",
  "pending",
  "uploaded",
  "processing",
  "indexed",
  "failed",
] as const

const EDITABLE_STATUSES = [
  "pending",
  "uploaded",
  "processing",
  "indexed",
  "failed",
] as const

function statusVariant(status: string) {
  if (status === "failed") return "destructive" as const
  if (status === "indexed") return "secondary" as const
  return "outline" as const
}

function EditDocumentDialog({
  document,
  onClose,
}: {
  document: AdminDocument
  onClose: () => void
}) {
  const [filename, setFilename] = React.useState(document.filename)
  const [status, setStatus] = React.useState(document.status)
  const updateDocument = useUpdateDocumentMutation()

  const handleSave = () => {
    updateDocument.mutate(
      {
        documentId: document.id,
        ...(filename !== document.filename ? { filename } : {}),
        ...(status !== document.status ? { status } : {}),
      },
      {
        onSuccess: () => {
          toast.success("Document updated")
          onClose()
        },
        onError: (error) => toast.error(error.message),
      }
    )
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit document</DialogTitle>
          <DialogDescription>
            Update the filename or ingestion status.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="filename">Filename</Label>
            <Input
              id="filename"
              value={filename}
              onChange={(event) => setFilename(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="status">Status</Label>
            <Select
              value={status}
              onValueChange={(value) => setStatus(value as string)}
            >
              <SelectTrigger id="status" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EDITABLE_STATUSES.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={updateDocument.isPending}>
            Save changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function AdminDocumentsTable() {
  const [pageIndex, setPageIndex] = React.useState(0)
  const [status, setStatus] = React.useState<string>("all")
  const [searchInput, setSearchInput] = React.useState("")
  const [search, setSearch] = React.useState("")
  const [previewDoc, setPreviewDoc] = React.useState<AdminDocument | null>(null)
  const [editDoc, setEditDoc] = React.useState<AdminDocument | null>(null)
  const [deleteDoc, setDeleteDoc] = React.useState<AdminDocument | null>(null)

  React.useEffect(() => {
    const timeout = setTimeout(() => {
      setSearch(searchInput)
      setPageIndex(0)
    }, 300)
    return () => clearTimeout(timeout)
  }, [searchInput])

  const { data, isLoading } = useAdminDocumentsQuery({
    status: status === "all" ? "" : status,
    search,
    page: pageIndex + 1,
    pageSize: PAGE_SIZE,
  })
  const deleteDocument = useDeleteDocumentMutation()

  const confirmDelete = () => {
    if (!deleteDoc) return
    const target = deleteDoc
    deleteDocument.mutate(target.id, {
      onSuccess: () => toast.success(`Deleted ${target.filename}`),
      onError: (error) => toast.error(error.message),
    })
    setDeleteDoc(null)
  }

  const columns: ColumnDef<AdminDocument>[] = [
    {
      accessorKey: "filename",
      header: "Filename",
      cell: ({ row }) => (
        <button
          type="button"
          onClick={() => setPreviewDoc(row.original)}
          className="block max-w-64 truncate text-left font-medium text-primary hover:underline"
          title={row.original.filename}
        >
          {row.original.filename}
        </button>
      ),
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => (
        <Badge variant={statusVariant(row.original.status)}>
          {row.original.status}
        </Badge>
      ),
    },
    {
      accessorKey: "errorMessage",
      header: "Error",
      cell: ({ row }) => {
        const message = row.original.errorMessage
        if (!message) return <span className="text-muted-foreground">—</span>
        return (
          <Tooltip>
            <TooltipTrigger
              render={<span className="block max-w-48 truncate" />}
            >
              {message}
            </TooltipTrigger>
            <TooltipContent className="max-w-96">{message}</TooltipContent>
          </Tooltip>
        )
      },
    },
    {
      accessorKey: "size",
      header: "Size",
      cell: ({ row }) =>
        row.original.size !== null
          ? `${(row.original.size / 1024).toFixed(1)} KB`
          : "—",
    },
    {
      accessorKey: "userId",
      header: "User",
      cell: ({ row }) => (
        <span className="font-mono text-xs">
          {row.original.userId.slice(0, 8)}
        </span>
      ),
    },
    {
      accessorKey: "notebookId",
      header: "Notebook",
      cell: ({ row }) => (
        <span className="font-mono text-xs">
          {row.original.notebookId.slice(0, 8)}
        </span>
      ),
    },
    {
      accessorKey: "createdAt",
      header: "Created",
      cell: ({ row }) => new Date(row.original.createdAt).toLocaleString(),
    },
    {
      id: "actions",
      cell: ({ row }) => {
        const document = row.original
        return (
          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant="ghost" size="icon" className="size-8" />}
            >
              <EllipsisVerticalIcon className="size-4" />
              <span className="sr-only">Open actions</span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setPreviewDoc(document)}>
                View file
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setEditDoc(document)}>
                Edit metadata
              </DropdownMenuItem>
              <DropdownMenuItem
                variant="destructive"
                onClick={() => setDeleteDoc(document)}
              >
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )
      },
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Input
          placeholder="Search by filename..."
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          className="max-w-sm"
        />
        <Select
          value={status}
          onValueChange={(value) => {
            setStatus(value as string)
            setPageIndex(0)
          }}
        >
          <SelectTrigger className="ml-auto w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUSES.map((option) => (
              <SelectItem key={option} value={option}>
                {option === "all" ? "All statuses" : option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {isLoading || !data ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <DataTable
          columns={columns}
          data={data.items}
          pageCount={Math.ceil(data.total / PAGE_SIZE)}
          pagination={{ pageIndex, pageSize: PAGE_SIZE }}
          onPaginationChange={(pagination) =>
            setPageIndex(pagination.pageIndex)
          }
          emptyMessage="No documents found."
        />
      )}

      {previewDoc && (
        <React.Suspense fallback={null}>
          <DocumentPreviewDialog
            document={previewDoc}
            onClose={() => setPreviewDoc(null)}
          />
        </React.Suspense>
      )}
      {editDoc && (
        <EditDocumentDialog
          document={editDoc}
          onClose={() => setEditDoc(null)}
        />
      )}

      <AlertDialog
        open={deleteDoc !== null}
        onOpenChange={(open) => !open && setDeleteDoc(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete document</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteDoc
                ? `Permanently delete "${deleteDoc.filename}" and its indexed chunks? This cannot be undone.`
                : ""}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
