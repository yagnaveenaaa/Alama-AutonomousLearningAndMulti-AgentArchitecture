"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api } from "@/shared/api/client";
import { TaskStateLabel } from "@/features/tasks/TaskStateLabel";
import { ui } from "@/shared/ui/PageShell";

export function TaskList({ limit }: { limit?: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => api.listTasks(),
  });

  if (isLoading) {
    return <p className={ui.empty}>Loading tasks…</p>;
  }

  const items = (data ?? []).slice(0, limit ?? data?.length);
  if (!items.length) {
    return <p className={ui.empty}>No tasks yet. Start from Chat.</p>;
  }

  return (
    <div className={ui.stack}>
      {items.map((task) => (
        <Link key={task.id} href={`/tasks/${task.id}`} className={ui.row}>
          <div>
            <strong>{task.title}</strong>
            <div className={ui.meta}>
              {task.repositoryName} · {new Date(task.createdAt).toLocaleString()}
            </div>
          </div>
          <TaskStateLabel state={task.state} />
        </Link>
      ))}
    </div>
  );
}
