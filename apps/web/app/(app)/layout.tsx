import { redirect } from "next/navigation";

import { DashboardHeaderProvider } from "@/components/providers/DashboardHeaderProvider";
import { AppShell } from "@/components/shell/AppShell";
import { createClient } from "@/lib/supabase/server";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <DashboardHeaderProvider>
      <AppShell email={user.email}>{children}</AppShell>
    </DashboardHeaderProvider>
  );
}
