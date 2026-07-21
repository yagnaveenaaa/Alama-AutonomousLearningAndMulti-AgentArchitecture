import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC = new Set(["/login", "/health"]);

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC.has(pathname) || pathname.startsWith("/_next") || pathname === "/favicon.ico") {
    return NextResponse.next();
  }

  const session = request.cookies.get("alama_session");
  if (!session) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }

  const response = NextResponse.next();
  if (!request.cookies.get("alama_tenant")) {
    response.cookies.set("alama_tenant", "local-tenant", {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
    });
  }
  return response;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
