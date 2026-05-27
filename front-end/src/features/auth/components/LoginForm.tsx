"use client";

import { useForm } from "@tanstack/react-form";
import { GalleryVerticalEnd } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { loginAction } from "@/features/auth/services/actions";
import {
  loginSchema,
  type AuthActionState,
  type LoginValues,
} from "@/features/auth/types";
import { cn } from "@/utils";

const initialAuthActionState: AuthActionState = {
  step: "details",
};

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const [state, setState] = useState<AuthActionState>(initialAuthActionState);
  const form = useForm({
    defaultValues: {
      email: state.email ?? "",
      password: "",
    } satisfies LoginValues,
    validators: {
      onSubmit: loginSchema,
    },
    onSubmit: async ({ value }) => {
      setState(initialAuthActionState);

      const formData = new FormData();
      formData.set("email", value.email);
      formData.set("password", value.password);

      const result = await loginAction(initialAuthActionState, formData);
      setState(result);
    },
  });

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <form
        onInvalidCapture={(event) => {
          event.preventDefault();
          void form.validate("submit");
        }}
        onSubmit={(event) => {
          event.preventDefault();
          event.stopPropagation();
          void form.handleSubmit();
        }}
      >
        <FieldGroup>
          <div className="flex flex-col items-center gap-2 text-center">
            <Link
              href="/"
              className="flex flex-col items-center gap-2 font-medium"
            >
              <div className="flex size-8 items-center justify-center rounded-md">
                <GalleryVerticalEnd className="size-6" />
              </div>
              <span className="sr-only">Personal RAG</span>
            </Link>
            <h1 className="text-xl font-bold">Welcome to Personal RAG</h1>
            <FieldDescription>
              Don&apos;t have an account? <Link href="/register" className="underline underline-offset-4 hover:text-primary">Sign up</Link>
            </FieldDescription>
          </div>

          <form.Field name="email">
            {(field) => {
              const isInvalid = Boolean(
                field.state.meta.errors.length || state.fieldErrors?.email
              );

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
              );
            }}
          </form.Field>

          <form.Field name="password">
            {(field) => {
              const isInvalid = Boolean(
                field.state.meta.errors.length || state.fieldErrors?.password
              );

              return (
                <Field data-invalid={isInvalid}>
                  <div className="flex items-center justify-between">
                    <FieldLabel htmlFor={field.name}>Password</FieldLabel>
                  </div>
                  <Input
                    id={field.name}
                    name={field.name}
                    type="password"
                    autoComplete="current-password"
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(event) => field.handleChange(event.target.value)}
                    aria-invalid={isInvalid}
                    required
                  />
                  <FieldError errors={field.state.meta.errors} />
                  <FieldError>{state.fieldErrors?.password}</FieldError>
                </Field>
              );
            }}
          </form.Field>

          {state.formError ? <FieldError>{state.formError}</FieldError> : null}

          <form.Subscribe selector={(formState) => formState.isSubmitting}>
            {(isSubmitting) => (
              <Field>
                <Button type="submit" className="w-full" disabled={isSubmitting}>
                  {isSubmitting ? "Signing in..." : "Sign in"}
                </Button>
              </Field>
            )}
          </form.Subscribe>
        </FieldGroup>
      </form>
      <FieldDescription className="px-6 text-center">
        By clicking continue, you agree to our <Link href="#" className="underline underline-offset-4 hover:text-primary">Terms of Service</Link>{" "}
        and <Link href="#" className="underline underline-offset-4 hover:text-primary">Privacy Policy</Link>.
      </FieldDescription>
    </div>
  );
}

