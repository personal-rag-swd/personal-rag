import { RegisterForm } from "@/features/auth/components/RegisterForm";

export default function RegisterPage() {
  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <RegisterForm className="w-full max-w-sm" />
    </main>
  );
}
