import Link from "next/link";

import { UsageWidget } from "@/features/analytics/UsageWidget";
import { RepoStatus } from "@/features/repos/RepoStatus";
import { TaskList } from "@/features/tasks/TaskList";
import { PageShell, ui } from "@/shared/ui/PageShell";

import styles from "./page.module.css";

export default function DashboardPage() {
  return (
    <PageShell
      kicker="Workspace"
      title="Alama"
      lede="Tasks in motion, repository index health, and spend against your cell budget."
    >
      <div className={`${styles.dash} rise-delay`}>
        <div className={ui.actions}>
          <Link href="/chat" className={ui.button}>
            Start from chat
          </Link>
          <Link href="/tasks" className={`${ui.button} ${ui.buttonSecondary}`}>
            Browse tasks
          </Link>
        </div>

        <div className={styles.split}>
          <section>
            <h2 className={ui.sectionTitle}>Active work</h2>
            <TaskList limit={5} />
          </section>
          <div>
            <section>
              <h2 className={ui.sectionTitle}>Repositories</h2>
              <RepoStatus />
            </section>
            <section className={ui.section}>
              <h2 className={ui.sectionTitle}>Usage</h2>
              <UsageWidget />
            </section>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
