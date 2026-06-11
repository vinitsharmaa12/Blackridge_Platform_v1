"use client";

import type { ReactNode } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { createClient } from "@/lib/supabase/client";

type SignOutButtonProps = {
  renderTrigger?: (props: { onClick: () => void }) => ReactNode;
};

export function SignOutButton({ renderTrigger }: SignOutButtonProps) {
  const router = useRouter();

  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  if (renderTrigger) {
    return <>{renderTrigger({ onClick: signOut })}</>;
  }

  return (
    <Button variant="ghost" size="sm" onClick={signOut}>
      Sign out
    </Button>
  );
}
