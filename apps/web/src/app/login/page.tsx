import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ui } from "@/shared/ui/PageShell";

import styles from "./login.module.css";

async function signIn(formData: FormData) {
  "use server";
  const next = String(formData.get("next") || "/");
  const jar = await cookies();
  jar.set("alama_session", "local-dev-session", {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
  });
  jar.set("alama_tenant", "local-tenant", {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
  });
  redirect(next.startsWith("/") ? next : "/");
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const params = await searchParams;
  return (
    <div className={styles.login}>
      <div className={`${styles.stage} rise`}>
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden />
          Alama
        </div>
        <p className={`${styles.lede} rise-delay`}>
          Autonomous software engineering for your repositories. Sign in to continue
          to your cell.
        </p>
        <form action={signIn} className={styles.form}>
          <input type="hidden" name="next" value={params.next || "/"} />
          <button type="submit" className={ui.button}>
            Continue with SSO
          </button>
          <p className={styles.hint}>
            Local slice uses a BFF session cookie stand-in. Production uses OIDC PKCE.
          </p>
        </form>
      </div>
    </div>
  );
}
