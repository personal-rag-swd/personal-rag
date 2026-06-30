import { useEffect } from "react"
import { Loader2Icon, SparklesIcon } from "lucide-react"

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

const formSchema = z.object({
  detailLevel: z.enum(["simple", "intermediate", "detailed"]),
  instructions: z
    .string()
    .max(500, "Focus instructions must be at most 500 characters."),
})

const TOGGLE_ITEM_CLASS =
  "rounded border-border px-3 py-1.5 text-xs data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"

export function MindMapGenerateDialog({
  open,
  onOpenChange,
  isGenerating,
  onGenerate,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  isGenerating: boolean
  onGenerate: (
    detailLevel: "simple" | "intermediate" | "detailed",
    instructions: string
  ) => void
}) {
  const form = useForm({
    defaultValues: {
      detailLevel: "intermediate" as "simple" | "intermediate" | "detailed",
      instructions: "",
    },
    validators: {
      onSubmit: formSchema,
    },
    onSubmit: async ({ value }) => {
      onGenerate(value.detailLevel, value.instructions)
      form.reset()
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
          <DialogTitle>Generate mind map</DialogTitle>
          <DialogDescription>
            Configure the concept map depth and optional focus instructions. The
            generated output will appear in Studio.
          </DialogDescription>
        </DialogHeader>

        <form
          id="mind-map-generator-form"
          onSubmit={(event) => {
            event.preventDefault()
            form.handleSubmit()
          }}
          className="space-y-6"
        >
          <FieldGroup>
            <form.Field
              name="detailLevel"
              children={(field) => {
                const isInvalid =
                  field.state.meta.isTouched && !field.state.meta.isValid

                return (
                  <Field data-invalid={isInvalid}>
                    <FieldLabel htmlFor={field.name}>
                      Depth / Level of Detail
                    </FieldLabel>
                    <ToggleGroup
                      disabled={isGenerating}
                      value={[field.state.value]}
                      onValueChange={(value: string[]) => {
                        if (
                          value[0] === "simple" ||
                          value[0] === "intermediate" ||
                          value[0] === "detailed"
                        ) {
                          field.handleChange(value[0])
                        }
                      }}
                      variant="outline"
                      className="justify-start gap-2"
                    >
                      <ToggleGroupItem
                        value="simple"
                        className={TOGGLE_ITEM_CLASS}
                      >
                        Simple
                      </ToggleGroupItem>
                      <ToggleGroupItem
                        value="intermediate"
                        className={TOGGLE_ITEM_CLASS}
                      >
                        Intermediate
                      </ToggleGroupItem>
                      <ToggleGroupItem
                        value="detailed"
                        className={TOGGLE_ITEM_CLASS}
                      >
                        Detailed
                      </ToggleGroupItem>
                    </ToggleGroup>
                    <FieldDescription>
                      {field.state.value === "simple" &&
                        "Generates a high-level outline with a compact concept map."}
                      {field.state.value === "intermediate" &&
                        "Balanced representation with core branches and relationships."}
                      {field.state.value === "detailed" &&
                        "Deep concept network with more branches and sub-concepts."}
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

                return (
                  <Field data-invalid={isInvalid}>
                    <FieldLabel htmlFor={field.name}>
                      Focus instructions (Optional)
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
                        placeholder="Focus on specific topics or relationships."
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
                    <FieldDescription>
                      Provide custom instructions to guide the concept mapping
                      process.
                    </FieldDescription>
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
            form="mind-map-generator-form"
            disabled={isGenerating}
            className="w-full gap-2"
          >
            {isGenerating ? (
              <>
                <Loader2Icon className="size-4 animate-spin" />
                Generating mind map...
              </>
            ) : (
              <>
                <SparklesIcon className="size-4" />
                Generate mind map
              </>
            )}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
