"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import styles from "./SiteHeader.module.css";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/tasks", label: "Tasks" },
  { href: "/chat", label: "Chat" },
];

export function SiteHeader() {
  const pathname = usePathname();
  if (pathname === "/login") {
    return null;
  }

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link href="/" className={styles.brand} aria-label="Alama home">
          <span className={styles.brandMark} aria-hidden />
          Alama
        </Link>
        <nav className={styles.nav} aria-label="Primary">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              data-active={
                link.href === "/"
                  ? pathname === "/"
                  : pathname === link.href || pathname.startsWith(`${link.href}/`)
              }
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
