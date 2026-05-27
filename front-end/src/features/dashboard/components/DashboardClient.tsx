import * as React from "react";
import { useForm } from "@tanstack/react-form";
import { useNavigate } from "react-router-dom";

import { useNotebooks } from "@/features/notebooks/store/notebook-store";
import { useCreateNotebookMutation, useUpdateNotebookMutation } from "@/features/notebooks/api";
import { notebookSchema, type Notebook } from "@/features/notebooks/types";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SearchIcon,
  PlusIcon,
  BookOpenIcon,
  Trash2Icon,
  MoreVerticalIcon,
  FileTextIcon,
  MessageSquareIcon,
  TagIcon,
  SparklesIcon,
  AlertCircleIcon,
  PencilIcon,
} from "lucide-react";
import { toast } from "sonner";

function formatDateLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function formatActivityLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60_000) return "Just now";
  if (diffMs < 3_600_000) return `${Math.floor(diffMs / 60_000)}m ago`;
  if (diffMs < 86_400_000) return `${Math.floor(diffMs / 3_600_000)}h ago`;
  return formatDateLabel(value);
}

export function DashboardClient() {
  const {
    notebooks,
    selectNotebook,
    addNotebook,
    deleteNotebook,
    updateNotebook,
  } = useNotebooks();

  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = React.useState("");
  const [sortBy, setSortBy] = React.useState<"lastActive" | "name" | "documentCount">("lastActive");

  // Modal States
  const [isCreateOpen, setIsCreateOpen] = React.useState(false);
  const [notebookToUpdate, setNotebookToUpdate] = React.useState<Notebook | null>(null);

  // Filter and Sort Notebooks
  const filteredNotebooks = React.useMemo(() => {
    let result = [...notebooks];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (nb) =>
          nb.name.toLowerCase().includes(q) ||
          nb.description.toLowerCase().includes(q) ||
          nb.tags.some((tag) => tag.toLowerCase().includes(q))
      );
    }

    result.sort((a, b) => {
      if (sortBy === "name") {
        return a.name.localeCompare(b.name);
      }
      if (sortBy === "documentCount") {
        return b.documentCount - a.documentCount;
      }
      return new Date(b.lastActiveAt).getTime() - new Date(a.lastActiveAt).getTime();
    });

    return result;
  }, [notebooks, searchQuery, sortBy]);

  const handleDeleteNotebook = (id: string, name: string) => {
    deleteNotebook(id);
    toast.success("Notebook deleted", {
      description: `"${name}" was deleted successfully.`,
    });
  };

  return (
    <main className="flex flex-1 flex-col bg-background select-none animate-in fade-in-50 duration-500">
      <div className="@container/main flex flex-1 flex-col gap-6 p-4 lg:p-6">

        {/* Action / Control Row */}
        <div className="mb-8 mt-5 flex flex-col sm:flex-row gap-3 justify-between items-stretch sm:items-center lg:mb-10">
          <div className="relative flex-1">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="Search workspaces by name, description, tags..."
              className="pl-9 h-10 border-border/80 bg-card/50 hover:border-primary/30 focus:border-primary/50 focus:ring-primary/10 transition-all rounded-xl"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 bg-card/50 border border-border rounded-xl px-2.5 h-10 select-none">
              <span className="text-xs text-muted-foreground font-medium shrink-0">Sort:</span>
              <select
                className="bg-transparent text-xs font-semibold text-foreground focus:outline-hidden cursor-pointer"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as "lastActive" | "name" | "documentCount")}
              >
                <option value="lastActive">Recently Active</option>
                <option value="name">Alphabetical</option>
                <option value="documentCount">Doc Count</option>
              </select>
            </div>

            <Button
              className="h-10 bg-primary hover:bg-primary/95 text-primary-foreground font-semibold px-4 rounded-xl shadow-xs transition-all duration-300 hover:shadow-md flex items-center gap-1.5"
              onClick={() => setIsCreateOpen(true)}
            >
              <PlusIcon className="size-4 shrink-0" />
              <span>New Notebook</span>
            </Button>
          </div>
        </div>

        {/* Notebooks Grid Section */}
        {filteredNotebooks.length > 0 ? (
          <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
            {filteredNotebooks.map((notebook) => {
              return (
                <Card
                  key={notebook.id}
                  size="sm"
                  onClick={() => {
                    selectNotebook(notebook.id);
                    void navigate(`/notebook/${notebook.id}`);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      selectNotebook(notebook.id);
                      void navigate(`/notebook/${notebook.id}`);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  className="cursor-pointer border border-border/70 transition-colors hover:border-foreground/20 hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/30"
                >
                  <CardHeader>
                    <div className="flex min-w-0 items-start gap-3">
                      <div className="flex size-8 shrink-0 items-center justify-center rounded-xl border bg-background text-muted-foreground">
                        <BookOpenIcon className="size-4" />
                      </div>
                      <div className="min-w-0">
                        <CardTitle className="truncate text-sm font-medium">{notebook.name}</CardTitle>
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
                              e.stopPropagation();
                              setNotebookToUpdate(notebook);
                            }}
                          >
                            <PencilIcon data-icon="inline-start" />
                            <span>Edit Notebook</span>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive focus:bg-destructive/10 focus:text-destructive"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteNotebook(notebook.id, notebook.name);
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
                    <p className="min-h-10 text-sm leading-6 text-muted-foreground line-clamp-2">
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
                          <Badge variant="ghost">+{notebook.tags.length - 3}</Badge>
                        )}
                      </div>
                    )}
                  </CardContent>

                  <CardFooter className="border-t text-xs text-muted-foreground">
                    <div className="grid w-full grid-cols-3 items-center gap-3">
                      <span className="flex items-center gap-1.5">
                        <FileTextIcon className="size-3.5" />
                        <strong className="font-medium text-foreground">{notebook.documentCount}</strong> docs
                      </span>
                      <span className="flex items-center gap-1.5">
                        <MessageSquareIcon className="size-3.5" />
                        <strong className="font-medium text-foreground">{notebook.queryCount}</strong> queries
                      </span>
                      <span className="truncate text-right">
                        {formatActivityLabel(notebook.lastActiveAt)}
                      </span>
                    </div>
                  </CardFooter>
                </Card>
              );
            })}
          </div>
        ) : (
          /* Empty Search or Empty State Handler */
          <div className="flex flex-col items-center justify-center text-center p-12 border border-dashed border-border/80 rounded-2xl bg-card/25 min-h-[350px] mt-2">
            <div className="size-16 rounded-2xl bg-muted/50 flex items-center justify-center text-muted-foreground mb-4">
              {searchQuery ? <AlertCircleIcon className="size-8" /> : <SparklesIcon className="size-8" />}
            </div>
            {searchQuery ? (
              <>
                <h3 className="text-base font-bold text-foreground">No matching notebooks</h3>
                <p className="text-xs text-muted-foreground max-w-sm mt-1">
                  We couldn&apos;t find any notebooks matching &quot;{searchQuery}&quot;. Try adjusting your keywords or clearing the filter.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-4 rounded-xl font-semibold border-border/80 hover:bg-muted"
                  onClick={() => setSearchQuery("")}
                >
                  Clear Search
                </Button>
              </>
            ) : (
              <>
                <h3 className="text-base font-bold text-foreground">No Notebooks Found</h3>
                <p className="text-xs text-muted-foreground max-w-sm mt-1">
                  Create your first cognitive workspace to organize files, documents, and start generating responses.
                </p>
                <Button
                  size="sm"
                  className="mt-4 bg-primary hover:bg-primary/95 text-primary-foreground font-semibold px-4 rounded-xl shadow-xs"
                  onClick={() => setIsCreateOpen(true)}
                >
                  <PlusIcon className="size-4 mr-1 shrink-0" />
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
                addNotebook(notebook);
                toast.success("Notebook created", {
                  description: `"${notebook.name}" is now ready for use.`,
                });
                setIsCreateOpen(false);
              }}
              onClose={() => setIsCreateOpen(false)}
            />
          )}
        </Dialog>

        {/* Update Modal Dialog */}
        <Dialog open={Boolean(notebookToUpdate)} onOpenChange={(open) => !open && setNotebookToUpdate(null)}>
          {notebookToUpdate && (
            <UpdateNotebookDialogContent
              notebook={notebookToUpdate}
              onSuccess={(updatedNotebook) => {
                updateNotebook(updatedNotebook.id, updatedNotebook);
                toast.success("Notebook updated", {
                  description: `"${updatedNotebook.name}" was updated successfully.`,
                });
                setNotebookToUpdate(null);
              }}
              onClose={() => setNotebookToUpdate(null)}
            />
          )}
        </Dialog>
      </div>
    </main>
  );
}

function CreateNotebookDialogContent({
  onSuccess,
  onClose,
}: {
  onSuccess: (notebook: Notebook) => void;
  onClose: () => void;
}) {
  const createMutation = useCreateNotebookMutation();
  const [formError, setFormError] = React.useState("");

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
      setFormError("");
      try {
        const tagsArray = value.tags
          ? value.tags.split(",").map((t) => t.trim()).filter(Boolean)
          : [];
        const result = await createMutation.mutateAsync({
          name: value.name,
          description: value.description || "",
          tags: tagsArray,
        });
        onSuccess(result);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to create notebook.";
        setFormError(message);
      }
    },
  });

  return (
    <DialogContent className="sm:max-w-md select-none rounded-2xl border-border bg-card">
      <DialogHeader>
        <DialogTitle className="text-lg font-bold flex items-center gap-2">
          <SparklesIcon className="size-5 text-primary" />
          <span>Create Workspace Notebook</span>
        </DialogTitle>
        <DialogDescription className="text-xs text-muted-foreground">
          Set up a dedicated cognitive notebook for a specific topic, project, or department.
        </DialogDescription>
      </DialogHeader>

      <form
        onInvalidCapture={(e) => {
          e.preventDefault();
          void form.validate("submit");
        }}
        onSubmit={(e) => {
          e.preventDefault();
          e.stopPropagation();
          void form.handleSubmit();
        }}
        className="py-2"
      >
        <FieldGroup>
          <form.Field name="name">
            {(field) => {
              const isInvalid = Boolean(field.state.meta.errors.length);
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
              );
            }}
          </form.Field>

          <form.Field name="description">
            {(field) => {
              const isInvalid = Boolean(field.state.meta.errors.length);
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
              );
            }}
          </form.Field>

          <form.Field name="tags">
            {(field) => {
              const isInvalid = Boolean(field.state.meta.errors.length);
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
                  <FieldDescription>Separate tags with commas.</FieldDescription>
                  <FieldError errors={field.state.meta.errors} />
                </Field>
              );
            }}
          </form.Field>

          {formError ? <FieldError>{formError}</FieldError> : null}

          <form.Subscribe selector={(fs) => fs.isSubmitting}>
            {(isSubmitting) => (
              <DialogFooter className="gap-2 sm:gap-0 pt-3">
                <Button
                  type="button"
                  variant="ghost"
                  className="rounded-xl font-semibold border-border/60 hover:bg-muted"
                  onClick={onClose}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  className="bg-primary hover:bg-primary/95 text-primary-foreground font-semibold px-4 rounded-xl shadow-xs"
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
  );
}

function UpdateNotebookDialogContent({
  notebook,
  onSuccess,
  onClose,
}: {
  notebook: Notebook;
  onSuccess: (notebook: Notebook) => void;
  onClose: () => void;
}) {
  const updateMutation = useUpdateNotebookMutation();
  const [formError, setFormError] = React.useState("");

  const form = useForm({
    defaultValues: {
      name: notebook.name,
      description: notebook.description,
      tags: notebook.tags.join(", "),
    },
    validators: {
      onSubmit: notebookSchema,
    },
    onSubmit: async ({ value }) => {
      setFormError("");
      try {
        const tagsArray = value.tags
          ? value.tags.split(",").map((t) => t.trim()).filter(Boolean)
          : [];
        const result = await updateMutation.mutateAsync({
          id: notebook.id,
          name: value.name,
          description: value.description || "",
          tags: tagsArray,
        });
        onSuccess(result);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to update notebook.";
        setFormError(message);
      }
    },
  });

  return (
    <DialogContent className="sm:max-w-md select-none rounded-2xl border-border bg-card">
      <DialogHeader>
        <DialogTitle className="text-lg font-bold flex items-center gap-2">
          <PencilIcon className="size-5 text-primary" />
          <span>Edit Workspace Notebook</span>
        </DialogTitle>
        <DialogDescription className="text-xs text-muted-foreground">
          Modify the details of your cognitive notebook workspace.
        </DialogDescription>
      </DialogHeader>

      <form
        onInvalidCapture={(e) => {
          e.preventDefault();
          void form.validate("submit");
        }}
        onSubmit={(e) => {
          e.preventDefault();
          e.stopPropagation();
          void form.handleSubmit();
        }}
        className="py-2"
      >
        <FieldGroup>
          <form.Field name="name">
            {(field) => {
              const isInvalid = Boolean(field.state.meta.errors.length);
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
              );
            }}
          </form.Field>

          <form.Field name="description">
            {(field) => {
              const isInvalid = Boolean(field.state.meta.errors.length);
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
              );
            }}
          </form.Field>

          <form.Field name="tags">
            {(field) => {
              const isInvalid = Boolean(field.state.meta.errors.length);
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
                  <FieldDescription>Separate tags with commas.</FieldDescription>
                  <FieldError errors={field.state.meta.errors} />
                </Field>
              );
            }}
          </form.Field>

          {formError ? <FieldError>{formError}</FieldError> : null}

          <form.Subscribe selector={(fs) => fs.isSubmitting}>
            {(isSubmitting) => (
              <DialogFooter className="gap-2 sm:gap-0 pt-3">
                <Button
                  type="button"
                  variant="ghost"
                  className="rounded-xl font-semibold border-border/60 hover:bg-muted"
                  onClick={onClose}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  className="bg-primary hover:bg-primary/95 text-primary-foreground font-semibold px-4 rounded-xl shadow-xs"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Saving..." : "Save Changes"}
                </Button>
              </DialogFooter>
            )}
          </form.Subscribe>
        </FieldGroup>
      </form>
    </DialogContent>
  );
}
