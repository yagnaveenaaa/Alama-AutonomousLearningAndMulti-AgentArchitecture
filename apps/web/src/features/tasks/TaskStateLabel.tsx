import type { TaskState } from "@/shared/api/types";
import { ui } from "@/shared/ui/PageShell";

const LABELS: Record<TaskState, string> = {
  queued: "Queued",
  planning: "Planning",
  executing: "Executing",
  verifying: "Verifying",
  awaiting_approval: "Awaiting approval",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function TaskStateLabel({ state }: { state: TaskState }) {
  return <span className={ui.state}>{LABELS[state]}</span>;
}
