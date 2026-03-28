import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);

  const code = searchParams.get("code");
  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type") as string | null;
  const next = searchParams.get("next");

  const supabase = await createClient();

  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (error) {
      return NextResponse.redirect(new URL("/login?error=auth_error", origin));
    }
  } else if (token_hash && type) {
    const { error } = await supabase.auth.verifyOtp({
      token_hash,
      type: type as "signup" | "email" | "recovery" | "email_change" | "magiclink",
    });
    if (error) {
      return NextResponse.redirect(new URL("/login?error=auth_error", origin));
    }
  } else {
    return NextResponse.redirect(new URL("/login?error=auth_error", origin));
  }

  // Redirect based on type or next param
  if (type === "recovery") {
    return NextResponse.redirect(new URL("/reset-password", origin));
  }

  if (next) {
    return NextResponse.redirect(new URL(next, origin));
  }

  return NextResponse.redirect(new URL("/dashboard", origin));
}
