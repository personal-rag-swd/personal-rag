import * as React from "react"
import { useForm } from "@tanstack/react-form"
import { useNavigate } from "react-router-dom"

import { useNotebooks } from "@/features/notebooks/store/notebook-store"
import { useCreateNotebookMutation } from "@/features/notebooks/api"
import { notebookSchema, type Notebook } from "@/features/notebooks/types"
import { UpdateNotebookDialog } from "@/features/notebooks/components/UpdateNotebookDialog"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Field,
  FieldDescription,
  FieldError,
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  SearchIcon,
  PlusIcon,
  BookOpenIcon,
  Trash2Icon,
  MoreVerticalIcon,
  TagIcon,
  SparklesIcon,
  AlertCircleIcon,
  PencilIcon,
  ChevronDownIcon,
} from "lucide-react"
import { toast } from "sonner"

function formatDateLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date)
}

export function DashboardClient() {
  const {
    notebooks,
    selectNotebook,
    addNotebook,
    deleteNotebook,
    updateNotebook,
  } = useNotebooks()

  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = React.useState("")
  const [sortBy, setSortBy] = React.useState<"lastActive" | "name">(
    "lastActive"
  )

  // Modal States
  const [isCreateOpen, setIsCreateOpen] = React.useState(false)
  const [notebookToUpdate, setNotebookToUpdate] =
    React.useState<Notebook | null>(null)

  // Filter and Sort Notebooks
  const filteredNotebooks = React.useMemo(() => {
    let result = [...notebooks]

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      result = result.filter(
        (nb) =>
          nb.name.toLowerCase().includes(q) ||
          nb.description.toLowerCase().includes(q) ||
          nb.tags.some((tag) => tag.toLowerCase().includes(q))
      )
    }

    result.sort((a, b) => {
      if (sortBy === "name") {
        return a.name.localeCompare(b.name)
      }
      return (
        new Date(b.lastActiveAt).getTime() - new Date(a.lastActiveAt).getTime()
      )
    })

    return result
  }, [notebooks, searchQuery, sortBy])

  const handleDeleteNotebook = (id: string, name: string) => {
    deleteNotebook(id)
    toast.success("Notebook deleted", {
      description: `"${name}" was deleted successfully.`,
    })
  }

  return (
    <main className="flex flex-1 animate-in flex-col bg-background duration-500 fade-in-50 select-none">
      <div className="@container/main flex flex-1 flex-col gap-6 p-4 lg:p-6">
        {/* Action / Control Row */}
        <div className="mt-5 mb-8 flex flex-col items-stretch justify-between gap-3 sm:flex-row sm:items-center lg:mb-10">
          <div className="relative flex-1">
            <SearchIcon className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search workspaces by name, description, tags..."
              className="h-10 rounded-xl border-border/80 bg-card/50 pl-9 transition-all hover:border-primary/30 focus:border-primary/50 focus:ring-primary/10"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Select
              value={sortBy}
              onValueChange={(val) => setSortBy(val as "lastActive" | "name")}
            >
              <SelectTrigger
                className="h-10 rounded-xl border border-border/80 bg-card/50 px-3.5 text-xs font-medium text-foreground hover:bg-muted/30 focus-visible:ring-3 focus-visible:ring-ring/30 focus-visible:outline-none"
              >
                <div className="flex items-center gap-1 select-none">
                  <span className="text-muted-foreground font-medium">Sort:</span>
                  <SelectValue />
                </div>
              </SelectTrigger>
              <SelectContent className="min-w-44" align="end">
                <SelectItem value="lastActive">Recently Active</SelectItem>
                <SelectItem value="name">Alphabetical</SelectItem>
              </SelectContent>
            </Select>

            <Button
              className="flex h-10 items-center gap-1.5 rounded-xl bg-primary px-4 font-semibold text-primary-foreground shadow-xs transition-all duration-300 hover:bg-primary/95 hover:shadow-md"
              onClick={() => setIsCreateOpen(true)}
            >
              <PlusIcon className="size-4 shrink-0" />
              <span>New Notebook</span>
            </Button>
          </div>
        </div>

        {/* Notebooks Grid Section */}
        {filteredNotebooks.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredNotebooks.map((notebook) => {
              return (
                <Card
                  key={notebook.id}
                  size="sm"
                  onClick={() => {
                    selectNotebook(notebook.id)
                    void navigate(`/notebook/${notebook.id}`)
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      selectNotebook(notebook.id)
                      void navigate(`/notebook/${notebook.id}`)
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  className="cursor-pointer border border-border/70 transition-colors hover:border-foreground/20 hover:bg-muted/30 focus-visible:ring-3 focus-visible:ring-ring/30 focus-visible:outline-none"
                >
                  <CardHeader>
                    <div className="flex min-w-0 items-start gap-3">
                      <div className="flex size-8 shrink-0 items-center justify-center rounded-xl border bg-background text-muted-foreground">
                        <BookOpenIcon className="size-4" />
                      </div>
                      <div className="min-w-0">
                        <CardTitle className="truncate text-sm font-medium">
                          {notebook.name}
                        </CardTitle>
                        <CardDescription className="text-xs">
                          Created {formatDateLabel(notebook.createdAt)}
                        </CardDescription>
                      </div>
                    </div>

                    <CardAction>
                      <DropdownMenu>
                        <DropdownMenuTrigger
                          onClick={(e) => e.stopPropagation()}
                          render={
                            <Button
                              variant="ghost"
                              size="icon"
                              className="text-muted-foreground"
                            />
                          }
                        >
                          <MoreVerticalIcon />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent className="w-40" align="end">
                          <DropdownMenuItem
                            onClick={(e) => {
                              e.stopPropagation()
                              setNotebookToUpdate(notebook)
                            }}
                          >
                            <PencilIcon data-icon="inline-start" />
                            <span>Edit Notebook</span>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive focus:bg-destructive/10 focus:text-destructive"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDeleteNotebook(notebook.id, notebook.name)
                            }}
                          >
                            <Trash2Icon data-icon="inline-start" />
                            <span>Delete Notebook</span>
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </CardAction>
                  </CardHeader>

                  <CardContent className="flex flex-1 flex-col gap-4">
                    <p className="line-clamp-2 min-h-10 text-sm leading-6 text-muted-foreground">
                      {notebook.description || "No description provided."}
                    </p>

                    {notebook.tags && notebook.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {notebook.tags.slice(0, 3).map((tag) => (
                          <Badge key={tag} variant="outline">
                            <TagIcon data-icon="inline-start" />
                            {tag}
                          </Badge>
                        ))}
                        {notebook.tags.length > 3 && (
                          <Badge variant="ghost">
                            +{notebook.tags.length - 3}
                          </Badge>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              )
            })}
          </div>
        ) : (
          /* Empty Search or Empty State Handler */
          <div className="mt-2 flex min-h-[350px] flex-col items-center justify-center rounded-2xl border border-dashed border-border/80 bg-card/25 p-12 text-center">
            <div className="mb-4 flex size-16 items-center justify-center rounded-2xl bg-muted/50 text-muted-foreground">
              {searchQuery ? (
                <AlertCircleIcon className="size-8" />
              ) : (
                <SparklesIcon className="size-8" />
              )}
            </div>
            {searchQuery ? (
              <>
                <h3 className="text-base font-bold text-foreground">
                  No matching notebooks
                </h3>
                <p className="mt-1 max-w-sm text-xs text-muted-foreground">
                  We couldn&apos;t find any notebooks matching &quot;
                  {searchQuery}&quot;. Try adjusting your keywords or clearing
                  the filter.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-4 rounded-xl border-border/80 font-semibold hover:bg-muted"
                  onClick={() => setSearchQuery("")}
                >
                  Clear Search
                </Button>
              </>
            ) : (
              <>
                <h3 className="text-base font-bold text-foreground">
                  No Notebooks Found
                </h3>
                <p className="mt-1 max-w-sm text-xs text-muted-foreground">
                  Create your first cognitive workspace to organize files,
                  documents, and start generating responses.
                </p>
                <Button
                  size="sm"
                  className="mt-4 rounded-xl bg-primary px-4 font-semibold text-primary-foreground shadow-xs hover:bg-primary/95"
                  onClick={() => setIsCreateOpen(true)}
                >
                  <PlusIcon className="mr-1 size-4 shrink-0" />
                  <span>Create Notebook</span>
                </Button>
              </>
            )}
          </div>
        )}

        {/* Creation Modal Dialog */}
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          {isCreateOpen && (
            <CreateNotebookDialogContent
              onSuccess={(notebook) => {
                addNotebook(notebook)
                toast.success("Notebook created", {
                  description: `"${notebook.name}" is now ready for use.`,
                })
                setIsCreateOpen(false)
              }}
              onClose={() => setIsCreateOpen(false)}
            />
          )}
        </Dialog>

        {/* Update Modal Dialog */}
        {notebookToUpdate && (
          <UpdateNotebookDialog
            open={Boolean(notebookToUpdate)}
            onOpenChange={(open) => !open && setNotebookToUpdate(null)}
            notebook={notebookToUpdate}
            onSuccess={(updatedNotebook) => {
              updateNotebook(updatedNotebook.id, updatedNotebook)
              toast.success("Notebook updated", {
                description: `"${updatedNotebook.name}" was updated successfully.`,
              })
              setNotebookToUpdate(null)
            }}
            onClose={() => setNotebookToUpdate(null)}
          />
        )}
      </div>
    </main>
  )
}

export function CreateNotebookDialogContent({
  onSuccess,
  onClose,
}: {
  onSuccess: (notebook: Notebook) => void
  onClose: () => void
}) {
  const createMutation = useCreateNotebookMutation()
  const [formError, setFormError] = React.useState("")

  const form = useForm({
    defaultValues: {
      name: "",
      description: "",
      tags: "",
    },
    validators: {
      onSubmit: notebookSchema,
    },
    onSubmit: async ({ value }) => {
      setFormError("")
      try {
        const tagsArray = value.tags
          ? value.tags
              .split(",")
              .map((t) => t.trim())
              .filter(Boolean)
          : []
        const result = await createMutation.mutateAsync({
          name: value.name,
          description: value.description || "",
          tags: tagsArray,
        })
        onSuccess(result)
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to create notebook."
        setFormError(message)
      }
    },
  })

  return (
    <DialogContent className="rounded-2xl border-border bg-card select-none sm:max-w-md">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-lg font-bold">
          <SparklesIcon className="size-5 text-primary" />
          <span>Create Workspace Notebook</span>
        </DialogTitle>
        <DialogDescription className="text-xs text-muted-foreground">
          Set up a dedicated cognitive notebook for a specific topic, project,
          or department.
        </DialogDescription>
      </DialogHeader>

      <form
        onInvalidCapture={(e) => {
          e.preventDefault()
          void form.validate("submit")
        }}
        onSubmit={(e) => {
          e.preventDefault()
          e.stopPropagation()
          void form.handleSubmit()
        }}
        className="py-2"
      >
        <FieldGroup>
          <form.Field name="name">
            {(field) => {
              const isInvalid = Boolean(field.state.meta.errors.length)
              return (
                <Field data-invalid={isInvalid}>
                  <FieldLabel htmlFor={field.name}>Notebook Name</FieldLabel>
                  <Input
                    id={field.name}
                    name={field.name}
                    placeholder="e.g. AI Ethics Research, Product Specs..."
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(e) => field.handleChange(e.target.value)}
                    aria-invalid={isInvalid}
                    required
                  />
                  <FieldError errors={field.state.meta.errors} />
                </Field>
              )
            }}
          </form.Field>

          <form.Field name="description">
            {(field) => {
              const isInvalid = Boolean(field.state.meta.errors.length)
              return (
                <Field data-invalid={isInvalid}>
                  <FieldLabel htmlFor={field.name}>Description</FieldLabel>
                  <Textarea
                    id={field.name}
                    name={field.name}
                    placeholder="Explain what documents will go here and the scope of RAG queries..."
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(e) => field.handleChange(e.target.value)}
                    aria-invalid={isInvalid}
                  />
                  <FieldError errors={field.state.meta.errors} />
                </Field>
              )
            }}
          </form.Field>

          <form.Field name="tags">
            {(field) => {
              const isInvalid = Boolean(field.state.meta.errors.length)
              return (
                <Field data-invalid={isInvalid}>
                  <FieldLabel htmlFor={field.name}>Tags</FieldLabel>
                  <Input
                    id={field.name}
                    name={field.name}
                    placeholder="e.g. Research, PDF, Technical"
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(e) => field.handleChange(e.target.value)}
                    aria-invalid={isInvalid}
                  />
                  <FieldDescription>
                    Separate tags with commas.
                  </FieldDescription>
                  <FieldError errors={field.state.meta.errors} />
                </Field>
              )
            }}
          </form.Field>

          {formError ? <FieldError>{formError}</FieldError> : null}

          <form.Subscribe selector={(fs) => fs.isSubmitting}>
            {(isSubmitting) => (
              <DialogFooter className="gap-2 pt-3 sm:gap-0">
                <Button
                  type="button"
                  variant="ghost"
                  className="rounded-xl border-border/60 font-semibold hover:bg-muted"
                  onClick={onClose}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  className="rounded-xl bg-primary px-4 font-semibold text-primary-foreground shadow-xs hover:bg-primary/95"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Creating..." : "Create Workspace"}
                </Button>
              </DialogFooter>
            )}
          </form.Subscribe>
        </FieldGroup>
      </form>
    </DialogContent>
  )
}
