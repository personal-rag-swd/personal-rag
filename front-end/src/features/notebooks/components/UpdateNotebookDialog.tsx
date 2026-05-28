import * as React from "react";
import { useForm } from "@tanstack/react-form";
import { PencilIcon } from "lucide-react";

import { useUpdateNotebookMutation } from "@/features/notebooks/api";
import { notebookSchema, type Notebook } from "@/features/notebooks/types";

import { Button } from "@/components/ui/button";
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

type UpdateNotebookDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  notebook: Notebook;
  onSuccess: (updatedNotebook: Notebook) => void;
  onClose: () => void;
};

export function UpdateNotebookDialog({
  open,
  onOpenChange,
  notebook,
  onSuccess,
  onClose,
}: UpdateNotebookDialogProps) {
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
    <Dialog open={open} onOpenChange={onOpenChange}>
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
    </Dialog>
  );
}
