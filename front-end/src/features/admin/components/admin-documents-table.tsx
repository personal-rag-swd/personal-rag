import * as React from "react"
import type { ColumnDef } from "@tanstack/react-table"

import { Badge } from "@/components/ui/badge"
import { DataTable } from "@/components/ui/data-table"
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
import { useAdminDocumentsQuery } from "../api"
import type { AdminDocument } from "../types"

const PAGE_SIZE = 20

const STATUSES = [
  "all",
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

const columns: ColumnDef<AdminDocument>[] = [
  {
    accessorKey: "filename",
    header: "Filename",
    cell: ({ row }) => (
      <span className="max-w-64 truncate font-medium" title={row.original.filename}>
        {row.original.filename}
      </span>
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
      <span className="font-mono text-xs">{row.original.userId.slice(0, 8)}</span>
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
]

export function AdminDocumentsTable() {
  const [pageIndex, setPageIndex] = React.useState(0)
  const [status, setStatus] = React.useState<string>("all")

  const { data, isLoading } = useAdminDocumentsQuery({
    status: status === "all" ? "" : status,
    page: pageIndex + 1,
    pageSize: PAGE_SIZE,
  })

  return (
    <div className="flex flex-col gap-4">
      <Select
        value={status}
        onValueChange={(value) => {
          setStatus(value as string)
          setPageIndex(0)
        }}
      >
        <SelectTrigger className="w-44">
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
    </div>
  )
}
