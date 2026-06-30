import { useForm } from "@tanstack/react-form"
import { Eye, EyeOff } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import * as React from "react"
import { REGEXP_ONLY_DIGITS } from "input-otp"

import { AviaryLogo } from "@/components/branding/aviary-logo"
import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from "@/components/ui/input-otp"
import { useAuth } from "@/features/auth/store/auth-store"
import {
  forgotPasswordSchema,
  resetPasswordSchema,
  type AuthActionState,
} from "@/features/auth/types"
import { cn, getErrorMessage } from "@/lib/utils"

const initialState: AuthActionState = { step: "details" }

export function ForgotPasswordForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const [state, setState] = React.useState<AuthActionState>(initialState)
  const isOtpStep = state.step === "otp"
  const email = state.email ?? ""

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <div className="flex flex-col items-center gap-2 text-center">
        <Link to="/" className="flex flex-col items-center gap-2 font-medium">
          <div className="flex items-center justify-center">
            <AviaryLogo className="h-20 w-20 object-contain" />
          </div>
          <span className="sr-only">Personal RAG</span>
        </Link>
        <h1 className="text-xl font-bold">
          {isOtpStep ? "Set new password" : "Forgot password?"}
        </h1>
        <FieldDescription>
          {isOtpStep ? (
            <>
              Enter the code sent to{" "}
              <span className="font-medium text-foreground">{email}</span> and
              choose a new password.
            </>
          ) : (
            <>
              Enter your email and we&apos;ll send you a reset code.{" "}
              <Link
                to="/login"
                className="underline underline-offset-4 hover:text-primary"
              >
                Back to sign in
              </Link>
            </>
          )}
        </FieldDescription>
      </div>

      {isOtpStep ? (
        <ResetPasswordForm key={email} email={email} setState={setState} />
      ) : (
        <RequestResetForm state={state} setState={setState} />
      )}
    </div>
  )
}

function RequestResetForm({
  state,
  setState,
}: {
  state: AuthActionState
  setState: (s: AuthActionState) => void
}) {
  const { requestPasswordReset } = useAuth()

  const form = useForm({
    defaultValues: { email: state.email ?? "" },
    validators: { onSubmit: forgotPasswordSchema },
    onSubmit: async ({ value }) => {
      setState(initialState)
      try {
        await requestPasswordReset(value.email)
        setState({ step: "otp", email: value.email })
      } catch (err: unknown) {
        setState({
          step: "details",
          email: value.email,
          formError: getErrorMessage(err, "Failed to send reset code."),
        })
      }
    },
  })

  return (
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
    >
      <FieldGroup>
        <form.Field name="email">
          {(field) => {
            const isInvalid = Boolean(
              field.state.meta.errors.length || state.fieldErrors?.email
            )
            return (
              <Field data-invalid={isInvalid}>
                <FieldLabel htmlFor={field.name}>Email</FieldLabel>
                <Input
                  id={field.name}
                  name={field.name}
                  type="email"
                  placeholder="m@example.com"
                  autoComplete="email"
                  value={field.state.value}
                  onBlur={field.handleBlur}
                  onChange={(e) => field.handleChange(e.target.value)}
                  aria-invalid={isInvalid}
                  required
                />
                <FieldError errors={field.state.meta.errors} />
                <FieldError>{state.fieldErrors?.email}</FieldError>
              </Field>
            )
          }}
        </form.Field>

        {state.formError ? <FieldError>{state.formError}</FieldError> : null}

        <form.Subscribe selector={(s) => s.isSubmitting}>
          {(isSubmitting) => (
            <Field>
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Sending code..." : "Send reset code"}
              </Button>
            </Field>
          )}
        </form.Subscribe>
      </FieldGroup>
    </form>
  )
}

function ResetPasswordForm({
  email,
  setState,
}: {
  email: string
  setState: (s: AuthActionState) => void
}) {
  const { completePasswordReset } = useAuth()
  const navigate = useNavigate()
  const [formError, setFormError] = React.useState<string | undefined>()
  const [showPassword, setShowPassword] = React.useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = React.useState(false)

  const form = useForm({
    defaultValues: { otp: "", newPassword: "", confirmNewPassword: "" },
    validators: { onSubmit: resetPasswordSchema },
    onSubmit: async ({ value }) => {
      setFormError(undefined)
      try {
        await completePasswordReset(email, value.otp, value.newPassword)
        navigate("/login", { state: { passwordReset: true } })
      } catch (err: unknown) {
        setFormError(getErrorMessage(err, "Failed to reset password."))
      }
    },
  })

  return (
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
    >
      <FieldGroup>
        <form.Field name="otp">
          {(field) => {
            const isInvalid = Boolean(field.state.meta.errors.length)
            return (
              <Field data-invalid={isInvalid}>
                <FieldLabel htmlFor={field.name}>Reset code</FieldLabel>
                <div className="flex justify-center">
                  <InputOTP
                    id={field.name}
                    name={field.name}
                    maxLength={6}
                    pattern={REGEXP_ONLY_DIGITS}
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(val) => field.handleChange(val)}
                    aria-invalid={isInvalid}
                    containerClassName="justify-center"
                    autoFocus
                    required
                  >
                    <InputOTPGroup>
                      {Array.from({ length: 6 }).map((_, i) => (
                        <InputOTPSlot key={i} index={i} />
                      ))}
                    </InputOTPGroup>
                  </InputOTP>
                </div>
                <FieldError errors={field.state.meta.errors} />
              </Field>
            )
          }}
        </form.Field>

        <form.Field name="newPassword">
          {(field) => {
            const isInvalid = Boolean(field.state.meta.errors.length)
            return (
              <Field data-invalid={isInvalid}>
                <FieldLabel htmlFor={field.name}>New password</FieldLabel>
                <InputGroup>
                  <InputGroupInput
                    id={field.name}
                    name={field.name}
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    minLength={8}
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(e) => field.handleChange(e.target.value)}
                    aria-invalid={isInvalid}
                    required
                  />
                  <InputGroupAddon align="inline-end">
                    <InputGroupButton
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? (
                        <EyeOff className="size-4" />
                      ) : (
                        <Eye className="size-4" />
                      )}
                    </InputGroupButton>
                  </InputGroupAddon>
                </InputGroup>
                <FieldError errors={field.state.meta.errors} />
              </Field>
            )
          }}
        </form.Field>

        <form.Field
          name="confirmNewPassword"
          validators={{
            onChangeListenTo: ["newPassword"],
            onChange: ({ value, fieldApi }) => {
              const pw = fieldApi.form.getFieldValue("newPassword")
              if (value && value !== pw) return "Passwords do not match."
              return undefined
            },
          }}
        >
          {(field) => {
            const error = field.state.meta.errors[0]
            const errorMessage =
              typeof error === "string"
                ? error
                : (error as { message?: string } | undefined)?.message
            const isInvalid = Boolean(errorMessage)
            return (
              <Field data-invalid={isInvalid}>
                <FieldLabel htmlFor={field.name}>Confirm new password</FieldLabel>
                <InputGroup>
                  <InputGroupInput
                    id={field.name}
                    name={field.name}
                    type={showConfirmPassword ? "text" : "password"}
                    autoComplete="new-password"
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(e) => field.handleChange(e.target.value)}
                    aria-invalid={isInvalid}
                    required
                  />
                  <InputGroupAddon align="inline-end">
                    <InputGroupButton
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      aria-label={
                        showConfirmPassword
                          ? "Hide confirm password"
                          : "Show confirm password"
                      }
                    >
                      {showConfirmPassword ? (
                        <EyeOff className="size-4" />
                      ) : (
                        <Eye className="size-4" />
                      )}
                    </InputGroupButton>
                  </InputGroupAddon>
                </InputGroup>
                {errorMessage && <FieldError>{errorMessage}</FieldError>}
              </Field>
            )
          }}
        </form.Field>

        {formError ? <FieldError>{formError}</FieldError> : null}

        <form.Subscribe selector={(s) => s.isSubmitting}>
          {(isSubmitting) => (
            <Field>
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Resetting..." : "Reset password"}
              </Button>
            </Field>
          )}
        </form.Subscribe>

        <FieldDescription className="text-center">
          <button
            type="button"
            className="underline underline-offset-4 hover:text-primary"
            onClick={() => setState({ step: "details", email })}
          >
            Didn&apos;t receive a code? Go back
          </button>
        </FieldDescription>
      </FieldGroup>
    </form>
  )
}
