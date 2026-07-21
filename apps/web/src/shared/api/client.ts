import type {
  Approval,
  ChatMessage,
  RepoStatus,
  TaskEvent,
  TaskSummary,
  UsageSnapshot,
} from "@/shared/api/types";

const now = () => new Date().toISOString();

let tasks: TaskSummary[] = [
  {
    id: "task_01",
    title: "Harden JWT verification",
    objective: "Add TokenVerifier helper with tests and docs",
    state: "executing",
    repositoryId: "repo_01",
    repositoryName: "alama/platform",
    createdAt: now(),
    paused: false,
  },
  {
    id: "task_02",
    title: "Fix flaky retrieval tests",
    objective: "Stabilize hybrid retrieval contract suite",
    state: "awaiting_approval",
    repositoryId: "repo_02",
    repositoryName: "alama/retrieval",
    createdAt: now(),
    paused: false,
  },
  {
    id: "task_03",
    title: "Index status badge",
    objective: "Surface index generation health on repo page",
    state: "completed",
    repositoryId: "repo_01",
    repositoryName: "alama/platform",
    createdAt: now(),
    paused: false,
  },
];

const events: Record<string, TaskEvent[]> = {
  task_01: [
    {
      id: "ev1",
      sequence: 1,
      eventType: "com.alama.task.created.v1",
      actorType: "user",
      summary: "Task created",
      createdAt: now(),
    },
    {
      id: "ev2",
      sequence: 2,
      eventType: "com.alama.agent.plan_ready.v1",
      actorType: "agent",
      summary: "Planner published 1-step plan",
      createdAt: now(),
    },
    {
      id: "ev3",
      sequence: 3,
      eventType: "com.alama.agent.step_completed.v1",
      actorType: "agent",
      summary: "Coder applied patch via tool gateway",
      createdAt: now(),
    },
  ],
  task_02: [
    {
      id: "ev4",
      sequence: 1,
      eventType: "com.alama.task.created.v1",
      actorType: "user",
      summary: "Task created",
      createdAt: now(),
    },
    {
      id: "ev5",
      sequence: 2,
      eventType: "com.alama.task.approval_requested.v1",
      actorType: "system",
      summary: "Gate: protected_branch_write",
      createdAt: now(),
    },
  ],
};

const approvals: Record<string, Approval[]> = {
  task_02: [
    {
      id: "appr_01",
      gate: "protected_branch_write",
      status: "pending",
    },
  ],
};

let chat: ChatMessage[] = [
  {
    id: "msg_0",
    role: "assistant",
    content: "Describe an objective. Alama will create a task and stream progress.",
    createdAt: now(),
  },
];

function delay(ms = 120) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export const api = {
  async listTasks(): Promise<TaskSummary[]> {
    await delay();
    return [...tasks];
  },

  async getTask(id: string): Promise<TaskSummary | null> {
    await delay();
    return tasks.find((t) => t.id === id) ?? null;
  },

  async listEvents(taskId: string): Promise<TaskEvent[]> {
    await delay();
    return [...(events[taskId] ?? [])];
  },

  async listApprovals(taskId: string): Promise<Approval[]> {
    await delay();
    return [...(approvals[taskId] ?? [])];
  },

  async decideApproval(taskId: string, approvalId: string, decision: "approved" | "rejected") {
    await delay();
    const list = approvals[taskId] ?? [];
    const item = list.find((a) => a.id === approvalId);
    if (!item || item.status !== "pending") {
      throw new Error("Approval not pending");
    }
    item.status = decision;
    const task = tasks.find((t) => t.id === taskId);
    if (task) {
      task.state = decision === "approved" ? "executing" : "cancelled";
    }
    (events[taskId] ??= []).push({
      id: `ev_${Date.now()}`,
      sequence: (events[taskId]?.length ?? 0) + 1,
      eventType: "com.alama.task.approval_decided.v1",
      actorType: "user",
      summary: `Approval ${decision}`,
      createdAt: now(),
    });
    return item;
  },

  async listRepos(): Promise<RepoStatus[]> {
    await delay();
    return [
      {
        id: "repo_01",
        fullName: "alama/platform",
        indexState: "ready",
        lastSyncedAt: now(),
      },
      {
        id: "repo_02",
        fullName: "alama/retrieval",
        indexState: "indexing",
        lastSyncedAt: now(),
      },
    ];
  },

  async getUsage(): Promise<UsageSnapshot> {
    await delay();
    return {
      tokensUsed: 240_000,
      tokensBudget: 1_000_000,
      usdMicrosUsed: 1_250_000,
      usdMicrosBudget: 5_000_000,
    };
  },

  async listChat(): Promise<ChatMessage[]> {
    await delay();
    return [...chat];
  },

  async sendChat(objective: string): Promise<{ messages: ChatMessage[]; task: TaskSummary }> {
    await delay(180);
    const task: TaskSummary = {
      id: `task_${Math.random().toString(36).slice(2, 8)}`,
      title: objective.slice(0, 64),
      objective,
      state: "planning",
      repositoryId: "repo_01",
      repositoryName: "alama/platform",
      createdAt: now(),
      paused: false,
    };
    tasks = [task, ...tasks];
    events[task.id] = [
      {
        id: `ev_${task.id}_1`,
        sequence: 1,
        eventType: "com.alama.task.created.v1",
        actorType: "user",
        summary: "Created from chat",
        createdAt: now(),
      },
      {
        id: `ev_${task.id}_2`,
        sequence: 2,
        eventType: "com.alama.agent.workflow_started.v1",
        actorType: "system",
        summary: "Agent workflow started",
        createdAt: now(),
      },
    ];
    const userMsg: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: "user",
      content: objective,
      createdAt: now(),
      taskId: task.id,
    };
    const assistantMsg: ChatMessage = {
      id: `msg_${Date.now() + 1}`,
      role: "assistant",
      content: `Created task “${task.title}”. Planner is drafting steps against alama/platform.`,
      createdAt: now(),
      taskId: task.id,
    };
    chat = [...chat, userMsg, assistantMsg];
    return { messages: chat, task };
  },
};
