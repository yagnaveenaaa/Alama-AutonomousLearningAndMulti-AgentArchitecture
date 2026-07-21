"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import { TaskStateLabel } from "@/features/tasks/TaskStateLabel";
import { ui } from "@/shared/ui/PageShell";

export function TaskDetail({ taskId }: { taskId: string }) {
  const queryClient = useQueryClient();
  const taskQuery = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api.getTask(taskId),
  });
  const eventsQuery = useQuery({
    queryKey: ["task", taskId, "events"],
    queryFn: () => api.listEvents(taskId),
  });
  const approvalsQuery = useQuery({
    queryKey: ["task", taskId, "approvals"],
    queryFn: () => api.listApprovals(taskId),
  });

  const decide = useMutation({
    mutationFn: ({ approvalId, decision }: { approvalId: string; decision: "approved" | "rejected" }) =>
      api.decideApproval(taskId, approvalId, decision),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["task", taskId] }),
        queryClient.invalidateQueries({ queryKey: ["tasks"] }),
        queryClient.invalidateQueries({ queryKey: ["task", taskId, "events"] }),
        queryClient.invalidateQueries({ queryKey: ["task", taskId, "approvals"] }),
      ]);
    },
  });

  const task = taskQuery.data;
  if (taskQuery.isLoading) {
    return <p className={ui.empty}>Loading task…</p>;
  }
  if (!task) {
    return <p className={ui.empty}>Task not found.</p>;
  }

  const pending = (approvalsQuery.data ?? []).filter((a) => a.status === "pending");

  return (
    <div className="rise-delay">
      <div className={ui.row}>
        <div>
          <div className={ui.meta}>{task.repositoryName}</div>
          <p>{task.objective}</p>
        </div>
        <TaskStateLabel state={task.state} />
      </div>

      {pending.map((approval) => (
        <div key={approval.id} className={ui.banner} role="region" aria-label="Approval gate">
          <strong>Approval required</strong>
          <div className={ui.meta}>Gate: {approval.gate}</div>
          <div className={ui.actions}>
            <button
              type="button"
              className={ui.button}
              disabled={decide.isPending}
              onClick={() => decide.mutate({ approvalId: approval.id, decision: "approved" })}
            >
              Approve
            </button>
            <button
              type="button"
              className={`${ui.button} ${ui.buttonSecondary}`}
              disabled={decide.isPending}
              onClick={() => decide.mutate({ approvalId: approval.id, decision: "rejected" })}
            >
              Reject
            </button>
          </div>
        </div>
      ))}

      <section className={ui.section}>
        <h2 className={ui.sectionTitle}>Timeline</h2>
        <div className={ui.stack}>
          {(eventsQuery.data ?? []).map((event) => (
            <div key={event.id} className={ui.row}>
              <div>
                <strong>{event.summary}</strong>
                <div className={ui.meta}>
                  {event.eventType} · {event.actorType}
                </div>
              </div>
              <span className={ui.meta}>#{event.sequence}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
