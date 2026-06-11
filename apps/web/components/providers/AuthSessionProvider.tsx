"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { createClient } from "@/lib/supabase/client";

/** Redirect to login when the Supabase session ends mid-session. */
export function AuthSessionProvider({ children }: { children: ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    const supabase = createClient();
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event) => {
      if (event === "SIGNED_OUT") {
        router.push("/login");
        router.refresh();
      }
    });
    return () => subscription.unsubscribe();
  }, [router]);

  return children;
}
