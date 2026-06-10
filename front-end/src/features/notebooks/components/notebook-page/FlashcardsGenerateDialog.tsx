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

export type FlashcardCount = "fewer" | "standard" | "more"
export type FlashcardDifficulty = "easy" | "medium" | "hard"

const formSchema = z.object({
  numberOfCards: z.enum(["fewer", "standard", "more"]),
  difficulty: z.enum(["easy", "medium", "hard"]),
  instructions: z
    .string()
    .max(500, "Instructions must be at most 500 characters."),
})

const TOGGLE_ITEM_CLASS =
  "rounded border-border px-3 py-1.5 text-xs data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"

export function FlashcardsGenerateDialog({
  open,
  onOpenChange,
  isGenerating,
  onGenerate,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  isGenerating: boolean
  onGenerate: (
    numberOfCards: FlashcardCount,
    difficulty: FlashcardDifficulty,
    instructions: string
  ) => void
}) {
  const form = useForm({
    defaultValues: {
      numberOfCards: "standard" as FlashcardCount,
      difficulty: "medium" as FlashcardDifficulty,
      instructions: "",
    },
    validators: {
      onSubmit: formSchema,
    },
    onSubmit: async ({ value }) => {
      onGenerate(value.numberOfCards, value.difficulty, value.instructions)
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
          <DialogTitle>Customize flashcards</DialogTitle>
          <DialogDescription>
            Choose how many cards and how challenging they should be. The
            generated cards will appear in Studio.
          </DialogDescription>
        </DialogHeader>

        <form
          id="flashcards-generator-form"
          onSubmit={(event) => {
            event.preventDefault()
            form.handleSubmit()
          }}
          className="space-y-6"
        >
          <FieldGroup>
            <form.Field
              name="numberOfCards"
              children={(field) => (
                <Field>
                  <FieldLabel htmlFor={field.name}>Number of cards</FieldLabel>
                  <ToggleGroup
                    disabled={isGenerating}
                    value={[field.state.value]}
                    onValueChange={(value: string[]) => {
                      if (
                        value[0] === "fewer" ||
                        value[0] === "standard" ||
                        value[0] === "more"
                      ) {
                        field.handleChange(value[0])
                      }
                    }}
                    variant="outline"
                    className="justify-start gap-2"
                  >
                    <ToggleGroupItem value="fewer" className={TOGGLE_ITEM_CLASS}>
                      Fewer
                    </ToggleGroupItem>
                    <ToggleGroupItem
                      value="standard"
                      className={TOGGLE_ITEM_CLASS}
                    >
                      Standard
                    </ToggleGroupItem>
                    <ToggleGroupItem value="more" className={TOGGLE_ITEM_CLASS}>
                      More
                    </ToggleGroupItem>
                  </ToggleGroup>
                  <FieldDescription>
                    {field.state.value === "fewer" &&
                      "Around 10 cards for a quick review."}
                    {field.state.value === "standard" &&
                      "Around 20 cards (default)."}
                    {field.state.value === "more" &&
                      "Around 30 cards for thorough study."}
                  </FieldDescription>
                </Field>
              )}
            />

            <form.Field
              name="difficulty"
              children={(field) => (
                <Field>
                  <FieldLabel htmlFor={field.name}>
                    Level of difficulty
                  </FieldLabel>
                  <ToggleGroup
                    disabled={isGenerating}
                    value={[field.state.value]}
                    onValueChange={(value: string[]) => {
                      if (
                        value[0] === "easy" ||
                        value[0] === "medium" ||
                        value[0] === "hard"
                      ) {
                        field.handleChange(value[0])
                      }
                    }}
                    variant="outline"
                    className="justify-start gap-2"
                  >
                    <ToggleGroupItem value="easy" className={TOGGLE_ITEM_CLASS}>
                      Easy
                    </ToggleGroupItem>
                    <ToggleGroupItem value="medium" className={TOGGLE_ITEM_CLASS}>
                      Medium
                    </ToggleGroupItem>
                    <ToggleGroupItem value="hard" className={TOGGLE_ITEM_CLASS}>
                      Hard
                    </ToggleGroupItem>
                  </ToggleGroup>
                  <FieldDescription>
                    {field.state.value === "easy" &&
                      "Core terms and foundational facts."}
                    {field.state.value === "medium" &&
                      "Important concepts and connections (default)."}
                    {field.state.value === "hard" &&
                      "Subtle distinctions and deeper relationships."}
                  </FieldDescription>
                </Field>
              )}
            />

            <form.Field
              name="instructions"
              children={(field) => {
                const isInvalid =
                  field.state.meta.isTouched && !field.state.meta.isValid

                return (
                  <Field data-invalid={isInvalid}>
                    <FieldLabel htmlFor={field.name}>
                      Topic / focus (Optional)
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
                        placeholder='e.g. "Focus on key terms about microservices" or "Make 30 cards".'
                        rows={5}
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
                      Optionally narrow the topic, restrict to a source, or request
                      a specific number of cards (max 50).
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
            form="flashcards-generator-form"
            disabled={isGenerating}
            className="w-full gap-2"
          >
            {isGenerating ? (
              <>
                <Loader2Icon className="size-4 animate-spin" />
                Generating flashcards...
              </>
            ) : (
              <>
                <SparklesIcon className="size-4" />
                Generate flashcards
              </>
            )}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
