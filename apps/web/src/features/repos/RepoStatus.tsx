"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import { ui } from "@/shared/ui/PageShell";

export function RepoStatus() {
  const { data, isLoading } = useQuery({
    queryKey: ["repos"],
    queryFn: () => api.listRepos(),
  });

  if (isLoading) {
    return <p className={ui.empty}>Checking repositories…</p>;
  }

  return (
    <div className={ui.stack}>
      {(data ?? []).map((repo) => (
        <div key={repo.id} className={ui.row}>
          <div>
            <strong>{repo.fullName}</strong>
            <div className={ui.meta}>
              Synced {new Date(repo.lastSyncedAt).toLocaleString()}
            </div>
          </div>
          <span className={ui.state}>{repo.indexState}</span>
        </div>
      ))}
    </div>
  );
}
