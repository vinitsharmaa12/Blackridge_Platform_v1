"use client";

import { AppHeader } from "@/components/shell/AppHeader";

export function AppShell({
  children,
  email,
}: {
  children: React.ReactNode;
  email: string | undefined;
}) {
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <AppHeader email={email} />
      <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {children}
      </main>
    </div>
  );
}
