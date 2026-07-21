import { TaskDetail } from "@/features/tasks/TaskDetail";
import { PageShell } from "@/shared/ui/PageShell";

export default async function TaskDetailPage({
  params,
}: {
  params: Promise<{ taskId: string }>;
}) {
  const { taskId } = await params;
  return (
    <PageShell
      kicker="Task"
      title="Work detail"
      lede="Timeline, approvals, and agent progress for this objective."
    >
      <TaskDetail taskId={taskId} />
    </PageShell>
  );
}
