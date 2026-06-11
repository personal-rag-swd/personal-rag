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

export type QuizQuestionCount = "fewer" | "standard" | "more"
export type QuizDifficulty = "easy" | "medium" | "hard"

const formSchema = z.object({
  numberOfQuestions: z.enum(["fewer", "standard", "more"]),
  difficulty: z.enum(["easy", "medium", "hard"]),
  instructions: z
    .string()
    .max(500, "Instructions must be at most 500 characters."),
})

const TOGGLE_ITEM_CLASS =
  "rounded border-border px-3 py-1.5 text-xs data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"

export function QuizGenerateDialog({
  open,
  onOpenChange,
  isGenerating,
  onGenerate,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  isGenerating: boolean
  onGenerate: (
    numberOfQuestions: QuizQuestionCount,
    difficulty: QuizDifficulty,
    instructions: string
  ) => void
}) {
  const form = useForm({
    defaultValues: {
      numberOfQuestions: "standard" as QuizQuestionCount,
      difficulty: "medium" as QuizDifficulty,
      instructions: "",
    },
    validators: {
      onSubmit: formSchema,
    },
    onSubmit: async ({ value }) => {
      onGenerate(value.numberOfQuestions, value.difficulty, value.instructions)
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
          <DialogTitle>Customize quiz</DialogTitle>
          <DialogDescription>
            Choose how many questions and how challenging the quiz should be. The
            generated quiz will appear in Studio.
          </DialogDescription>
        </DialogHeader>

        <form
          id="quiz-generator-form"
          onSubmit={(event) => {
            event.preventDefault()
            form.handleSubmit()
          }}
          className="space-y-6"
        >
          <FieldGroup>
            <form.Field
              name="numberOfQuestions"
              children={(field) => (
                <Field>
                  <FieldLabel htmlFor={field.name}>
                    Number of questions
                  </FieldLabel>
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
                      "Around 10 questions for a quick check."}
                    {field.state.value === "standard" &&
                      "Around 20 questions (default)."}
                    {field.state.value === "more" &&
                      "Around 30 questions for thorough practice."}
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
                      "Recall and basic comprehension."}
                    {field.state.value === "medium" &&
                      "Application and analysis (default)."}
                    {field.state.value === "hard" &&
                      "Synthesis and nuanced distinctions."}
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
                        placeholder='e.g. "Focus on microservices and scalability" or "Make a 30-question quiz".'
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
                      a specific number of questions (max 50).
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
            form="quiz-generator-form"
            disabled={isGenerating}
            className="w-full gap-2"
          >
            {isGenerating ? (
              <>
                <Loader2Icon className="size-4 animate-spin" />
                Generating quiz...
              </>
            ) : (
              <>
                <SparklesIcon className="size-4" />
                Generate quiz
              </>
            )}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
