import { describe, expect, it } from "vitest";

import { api } from "@/shared/api/client";

describe("alama web api client", () => {
  it("lists seeded tasks", async () => {
    const tasks = await api.listTasks();
    expect(tasks.length).toBeGreaterThan(0);
    expect(tasks[0]?.title).toBeTruthy();
  });

  it("creates a task from chat", async () => {
    const { task, messages } = await api.sendChat("Add health probe to tool-gateway");
    expect(task.state).toBe("planning");
    expect(messages.at(-1)?.taskId).toBe(task.id);
  });
});
