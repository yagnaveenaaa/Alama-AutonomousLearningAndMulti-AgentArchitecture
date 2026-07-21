import { PageShell, ui } from "@/shared/ui/PageShell";

export default function NotFoundPage() {
  return (
    <PageShell kicker="404" title="Not found" lede="That route is outside this Alama cell.">
      <a href="/" className={ui.button}>
        Back to dashboard
      </a>
    </PageShell>
  );
}
