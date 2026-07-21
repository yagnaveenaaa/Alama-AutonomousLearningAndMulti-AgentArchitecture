import { TaskList } from "@/features/tasks/TaskList";
import { PageShell } from "@/shared/ui/PageShell";

export default function TasksPage() {
  return (
    <PageShell
      kicker="Tasks"
      title="Issues in flight"
      lede="Filterable task list for the active tenant. Open a task for timeline, plan, and approvals."
    >
      <section className="rise-delay" style={{ marginTop: "2rem" }}>
        <TaskList />
      </section>
    </PageShell>
  );
}
