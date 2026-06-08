import { z } from "zod"

export const emailSchema = z
  .string()
  .trim()
  .min(1, "Email is required.")
  .email("Enter a valid email address.")
  .toLowerCase()

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().trim().min(1, "Password is required."),
})

export const registrationSchema = z
  .object({
    email: emailSchema,
    password: z
      .string()
      .trim()
      .min(8, "Password must be at least 8 characters.")
      .max(128, "Password must be 128 characters or fewer."),
    confirmPassword: z.string().trim().min(1, "Please confirm your password."),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match.",
    path: ["confirmPassword"],
  })

export const verificationSchema = z.object({
  email: emailSchema,
  otp: z
    .string()
    .trim()
    .regex(/^\d{6}$/, "Enter the 6-digit code."),
})

export type LoginValues = z.input<typeof loginSchema>
export type RegistrationValues = z.input<typeof registrationSchema>
export type VerificationValues = z.input<typeof verificationSchema>

export type ApiErrorPayload = {
  detail?: string | Array<{ msg?: string; loc?: Array<string | number> }>
}

export type AuthActionState = {
  step?: "details" | "otp"
  email?: string
  formError?: string
  fieldErrors?: Partial<Record<"email" | "password" | "otp", string>>
}
