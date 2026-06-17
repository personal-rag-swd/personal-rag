import { useForm } from "@tanstack/react-form"
import { Eye, EyeOff } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import * as React from "react"

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
import { REGEXP_ONLY_DIGITS } from "input-otp"
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from "@/components/ui/input-otp"
import { useAuth } from "@/features/auth/store/auth-store"
import {
  registrationSchema,
  verificationSchema,
  type AuthActionState,
} from "@/features/auth/types"
import { cn } from "@/lib/utils"

const initialAuthActionState: AuthActionState = {
  step: "details",
}

export function RegisterForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const [registrationState, setRegistrationState] =
    React.useState<AuthActionState>(initialAuthActionState)
  const [verificationState, setVerificationState] =
    React.useState<AuthActionState>({
      step: "otp",
      email: registrationState.email,
    })

  const otpEmail = verificationState.email || registrationState.email || ""
  const isOtpStep = registrationState.step === "otp"

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
          {isOtpStep ? "Verify your email" : "Create account"}
        </h1>
        <FieldDescription>
          {isOtpStep ? (
            <>
              Enter the 6-digit code sent to{" "}
              <span className="font-medium text-foreground">{otpEmail}</span>.
            </>
          ) : (
            <>
              Already have an account?{" "}
              <Link
                to="/login"
                className="underline underline-offset-4 hover:text-primary"
              >
                Sign in
              </Link>
            </>
          )}
        </FieldDescription>
      </div>

      {isOtpStep ? (
        <VerificationForm
          key={otpEmail}
          email={otpEmail}
          state={verificationState}
          setState={setVerificationState}
        />
      ) : (
        <RegistrationDetailsForm
          state={registrationState}
          setState={setRegistrationState}
          setVerificationState={setVerificationState}
        />
      )}

      {!isOtpStep && (
        <FieldDescription className="px-6 text-center">
          By clicking continue, you agree to our{" "}
          <Link
            to="#"
            className="underline underline-offset-4 hover:text-primary"
          >
            Terms of Service
          </Link>{" "}
          and{" "}
          <Link
            to="#"
            className="underline underline-offset-4 hover:text-primary"
          >
            Privacy Policy
          </Link>
          .
        </FieldDescription>
      )}
    </div>
  )
}

function RegistrationDetailsForm({
  state,
  setState,
  setVerificationState,
}: {
  state: AuthActionState
  setState: (state: AuthActionState) => void
  setVerificationState: (state: AuthActionState) => void
}) {
  const { startRegistration } = useAuth()
  const [showPassword, setShowPassword] = React.useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = React.useState(false)

  const form = useForm({
    defaultValues: {
      email: state.email ?? "",
      password: "",
      confirmPassword: "",
    },
    validators: {
      onSubmit: registrationSchema,
    },
    onSubmit: async ({ value }) => {
      setState(initialAuthActionState)
      try {
        const result = await startRegistration(value.email, value.password)

        setState({ step: result.step, email: value.email })
        if (result.step === "otp") {
          setVerificationState({ step: "otp", email: value.email })
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to start registration."
        setState({
          step: "details",
          email: value.email,
          formError: message,
        })
      }
    },
  })

  return (
    <form
      onInvalidCapture={(event) => {
        event.preventDefault()
        void form.validate("submit")
      }}
      onSubmit={(event) => {
        event.preventDefault()
        event.stopPropagation()
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
                  onChange={(event) => field.handleChange(event.target.value)}
                  aria-invalid={isInvalid}
                  required
                />
                <FieldError errors={field.state.meta.errors} />
                <FieldError>{state.fieldErrors?.email}</FieldError>
              </Field>
            )
          }}
        </form.Field>

        <form.Field name="password">
          {(field) => {
            const isInvalid = Boolean(
              field.state.meta.errors.length || state.fieldErrors?.password
            )

            return (
              <Field data-invalid={isInvalid}>
                <FieldLabel htmlFor={field.name}>Password</FieldLabel>
                <InputGroup>
                  <InputGroupInput
                    id={field.name}
                    name={field.name}
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    minLength={8}
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(event) => field.handleChange(event.target.value)}
                    aria-invalid={isInvalid}
                    required
                  />
                  <InputGroupAddon align="inline-end">
                    <InputGroupButton
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={
                        showPassword ? "Hide password" : "Show password"
                      }
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
                <FieldError>{state.fieldErrors?.password}</FieldError>
              </Field>
            )
          }}
        </form.Field>

        <form.Field
          name="confirmPassword"
          validators={{
            onChangeListenTo: ["password"],
            onChange: ({ value, fieldApi }) => {
              const password = fieldApi.form.getFieldValue("password")
              if (value && value !== password) return "Passwords do not match."
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
                <FieldLabel htmlFor={field.name}>Confirm password</FieldLabel>
                <InputGroup>
                  <InputGroupInput
                    id={field.name}
                    name={field.name}
                    type={showConfirmPassword ? "text" : "password"}
                    autoComplete="new-password"
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(event) => field.handleChange(event.target.value)}
                    aria-invalid={isInvalid}
                    required
                  />
                  <InputGroupAddon align="inline-end">
                    <InputGroupButton
                      onClick={() =>
                        setShowConfirmPassword(!showConfirmPassword)
                      }
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

        {state.formError ? <FieldError>{state.formError}</FieldError> : null}

        <form.Subscribe selector={(formState) => formState.isSubmitting}>
          {(isSubmitting) => (
            <Field>
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Sending code..." : "Continue"}
              </Button>
            </Field>
          )}
        </form.Subscribe>
      </FieldGroup>
    </form>
  )
}

function VerificationForm({
  email,
  state,
  setState,
}: {
  email: string
  state: AuthActionState
  setState: (state: AuthActionState) => void
}) {
  const { verifyRegistration } = useAuth()
  const navigate = useNavigate()

  const form = useForm({
    defaultValues: {
      email,
      otp: "",
    },
    validators: {
      onSubmit: verificationSchema,
    },
    onSubmit: async ({ value }) => {
      setState({ step: "otp", email })
      try {
        await verifyRegistration(email, value.otp)
        navigate("/login")
      } catch (err: unknown) {
        const message =
          err instanceof Error
            ? err.message
            : "Failed to verify registration code."
        setState({
          step: "otp",
          email,
          formError: message,
        })
      }
    },
  })

  return (
    <form
      onInvalidCapture={(event) => {
        event.preventDefault()
        void form.validate("submit")
      }}
      onSubmit={(event) => {
        event.preventDefault()
        event.stopPropagation()
        void form.handleSubmit()
      }}
    >
      <FieldGroup>
        <input type="hidden" name="email" value={email} />
        <form.Field name="otp">
          {(field) => {
            const isInvalid = Boolean(
              field.state.meta.errors.length || state.fieldErrors?.otp
            )

            return (
              <Field data-invalid={isInvalid}>
                <FieldLabel htmlFor={field.name}>Verification code</FieldLabel>
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
                    required
                  >
                    <InputOTPGroup>
                      {Array.from({ length: 6 }).map((_, index) => (
                        <InputOTPSlot key={index} index={index} />
                      ))}
                    </InputOTPGroup>
                  </InputOTP>
                </div>
                <FieldError errors={field.state.meta.errors} />
                <FieldError>{state.fieldErrors?.otp}</FieldError>
              </Field>
            )
          }}
        </form.Field>
        {state.formError ? <FieldError>{state.formError}</FieldError> : null}
        <form.Subscribe selector={(formState) => formState.isSubmitting}>
          {(isSubmitting) => (
            <Field>
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Verifying..." : "Verify email"}
              </Button>
            </Field>
          )}
        </form.Subscribe>
      </FieldGroup>
    </form>
  )
}
