import { useEffect } from "react"
import { SparklesIcon } from "lucide-react"
import { toast } from "sonner"

import { useForm } from "@tanstack/react-form"
import * as z from "zod"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupText,
  InputGroupTextarea,
} from "@/components/ui/input-group"
import { useGenerateNotebookReportMutation } from "@/features/notebooks/api"
import type { NotebookReport, ReportType } from "@/features/notebooks/types"
import { cn } from "@/lib/utils"

import { REPORT_TYPES, REPORT_TYPE_BY_ID } from "./reportTypes"

const formSchema = z
  .object({
    selectedType: z.custom<ReportType>(),
    instructions: z
      .string()
      .max(500, "Focus instructions must be at most 500 characters."),
  })
  .refine(
    (data) =>
      data.selectedType !== "custom" || data.instructions.trim().length > 0,
    {
      message: "Please describe what report you want.",
      path: ["instructions"],
    }
  )

export function ReportGenerateDialog({
  notebookId,
  open,
  onOpenChange,
  onGenerated,
}: {
  notebookId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onGenerated?: (report: NotebookReport) => void
}) {
  const generateMutation = useGenerateNotebookReportMutation(notebookId)

  const form = useForm({
    defaultValues: {
      selectedType: "custom" as ReportType,
      instructions: "",
    },
    validators: {
      onSubmit: formSchema,
    },
    onSubmit: async ({ value }) => {
      generateMutation.mutate(
        {
          reportType: value.selectedType,
          additionalInstructions: value.instructions.trim() || undefined,
        },
        {
          onSuccess: (report) => {
            toast.success("Report queued", {
              description: REPORT_TYPE_BY_ID[value.selectedType].label,
            })
            onGenerated?.(report)
            onOpenChange(false)
            form.reset()
          },
          onError: (error) => {
            toast.error("Failed to queue report", {
              description: error.message,
            })
          },
        }
      )
    },
  })

  useEffect(() => {
    if (!open) {
      form.reset()
    }
  }, [form, open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Generate report</DialogTitle>
          <DialogDescription>
            Choose a format and optional focus instructions. The report will be
            generated in the background and appear in Studio when ready.
          </DialogDescription>
        </DialogHeader>

        <form
          id="report-generator-form"
          onSubmit={(event) => {
            event.preventDefault()
            form.handleSubmit()
          }}
          className="space-y-6"
        >
          <FieldGroup>
            <form.Field
              name="selectedType"
              children={(field) => {
                const isInvalid =
                  field.state.meta.isTouched && !field.state.meta.isValid
                const activeMeta = REPORT_TYPE_BY_ID[field.state.value]

                return (
                  <Field data-invalid={isInvalid}>
                    <FieldLabel htmlFor={field.name}>Format</FieldLabel>
                    <ToggleGroup
                      disabled={generateMutation.isPending}
                      value={[field.state.value]}
                      onValueChange={(value: string[]) => {
                        if (value[0]) {
                          field.handleChange(value[0] as ReportType)
                        }
                      }}
                      variant="outline"
                      className="flex-wrap justify-start gap-2"
                    >
                      {REPORT_TYPES.map((reportType) => (
                        <ToggleGroupItem
                          key={reportType.id}
                          value={reportType.id}
                          className={cn(
                            "h-9 gap-1.5 rounded-full px-3.5 text-xs font-medium data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
                          )}
                        >
                          <span
                            className={cn(
                              "shrink-0 transition-colors",
                              field.state.value === reportType.id
                                ? "text-primary-foreground"
                                : "text-muted-foreground"
                            )}
                          >
                            {reportType.icon}
                          </span>
                          {reportType.shortLabel}
                        </ToggleGroupItem>
                      ))}
                    </ToggleGroup>
                    <FieldDescription>
                      {activeMeta.description}
                    </FieldDescription>
                    {isInvalid ? (
                      <FieldError errors={field.state.meta.errors} />
                    ) : null}
                  </Field>
                )
              }}
            />

            <form.Field
              name="instructions"
              children={(field) => {
                const isInvalid =
                  field.state.meta.isTouched && !field.state.meta.isValid
                const selectedType = form.state.values.selectedType
                const isCustom = selectedType === "custom"
                const activeMeta = REPORT_TYPE_BY_ID[selectedType]

                return (
                  <Field data-invalid={isInvalid}>
                    <FieldLabel htmlFor={field.name}>
                      {isCustom
                        ? "Your instructions"
                        : "Additional instructions (Optional)"}
                    </FieldLabel>
                    <InputGroup>
                      <InputGroupTextarea
                        id={field.name}
                        name={field.name}
                        value={field.state.value}
                        onBlur={field.handleBlur}
                        onChange={(event) =>
                          field.handleChange(event.target.value)
                        }
                        placeholder={activeMeta.placeholder}
                        rows={6}
                        className="min-h-24 resize-none text-xs text-foreground focus-visible:ring-primary"
                        aria-invalid={isInvalid}
                      />
                      <InputGroupAddon align="block-end">
                        <InputGroupText className="tabular-nums">
                          {field.state.value.length}/500 characters
                        </InputGroupText>
                      </InputGroupAddon>
                    </InputGroup>
                    {isInvalid ? (
                      <FieldError errors={field.state.meta.errors} />
                    ) : null}
                  </Field>
                )
              }}
            />
          </FieldGroup>

          <Button
            type="submit"
            form="report-generator-form"
            disabled={generateMutation.isPending}
            className="w-full gap-2"
          >
            <SparklesIcon className="size-4" />
            {generateMutation.isPending ? "Queuing..." : "Generate report"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
