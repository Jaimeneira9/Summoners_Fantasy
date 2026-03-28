import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

const PUBLIC_ROUTES = ["/login", "/signup", "/auth/callback", "/forgot-password", "/reset-password", "/confirm-email"];
const AUTH_REDIRECT = "/login";
const DEFAULT_PROTECTED = "/dashboard";
const ONBOARDING_ROUTE = "/onboarding";

export async function middleware(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // IMPORTANT: no llamar a otros métodos Supabase entre createServerClient y getUser
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname } = request.nextUrl;
  const isPublicRoute = PUBLIC_ROUTES.some((r) => pathname.startsWith(r));

  // Usuario auth intentando acceder a login/signup o root → dashboard
  if (user && (isPublicRoute || pathname === "/")) {
    return NextResponse.redirect(new URL(DEFAULT_PROTECTED, request.url));
  }

  // Usuario no auth intentando acceder a ruta protegida → login
  if (!user && !isPublicRoute) {
    return NextResponse.redirect(new URL(AUTH_REDIRECT, request.url));
  }

  // Onboarding guard: usuario auth sin onboarding completado → /onboarding
  if (user && !isPublicRoute && pathname !== ONBOARDING_ROUTE) {
    const onboardingCompleted =
      user.user_metadata?.onboarding_completed === true;
    if (!onboardingCompleted) {
      return NextResponse.redirect(new URL(ONBOARDING_ROUTE, request.url));
    }
  }

  // Inyectar x-pathname para que los Server Components puedan leer la ruta actual
  supabaseResponse.headers.set("x-pathname", pathname);

  return supabaseResponse;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
