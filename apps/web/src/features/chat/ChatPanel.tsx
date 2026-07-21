"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { api } from "@/shared/api/client";
import { ui } from "@/shared/ui/PageShell";

export function ChatPanel() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const messagesQuery = useQuery({
    queryKey: ["chat"],
    queryFn: () => api.listChat(),
  });

  const send = useMutation({
    mutationFn: (objective: string) => api.sendChat(objective),
    onSuccess: async () => {
      setDraft("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["chat"] }),
        queryClient.invalidateQueries({ queryKey: ["tasks"] }),
      ]);
    },
  });

  return (
    <div className="rise-delay">
      <div className={ui.stack}>
        {(messagesQuery.data ?? []).map((message) => (
          <div key={message.id} className={ui.row}>
            <div>
              <div className={ui.meta}>{message.role}</div>
              <p style={{ margin: "0.25rem 0 0" }}>{message.content}</p>
              {message.taskId ? (
                <Link href={`/tasks/${message.taskId}`} className={ui.meta}>
                  Open task →
                </Link>
              ) : null}
            </div>
          </div>
        ))}
      </div>

      <form
        className={ui.section}
        onSubmit={(event) => {
          event.preventDefault();
          const value = draft.trim();
          if (!value || send.isPending) {
            return;
          }
          send.mutate(value);
        }}
      >
        <label className={ui.meta} htmlFor="composer">
          Objective
        </label>
        <textarea
          id="composer"
          className={ui.textarea}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="e.g. Add rate-limit headers to the retrieval API"
        />
        <div className={ui.actions}>
          <button type="submit" className={ui.button} disabled={send.isPending || !draft.trim()}>
            {send.isPending ? "Creating task…" : "Start task"}
          </button>
        </div>
      </form>
    </div>
  );
}
