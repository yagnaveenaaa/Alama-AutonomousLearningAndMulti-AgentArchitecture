/**
 * Alama web API client.
 *
 * - Default: local in-browser mock (fast UI demos without backends)
 * - NEXT_PUBLIC_BFF_URL set: live GraphQL BFF (enable vertical slice on BFF)
 */

import type {
  Approval,
  ChatMessage,
  RepoStatus,
  TaskEvent,
  TaskState,
  TaskSummary,
  UsageSnapshot,
} from "@/shared/api/types";

const BFF_URL = (process.env.NEXT_PUBLIC_BFF_URL || "").replace(/\/$/, "");
const SUBJECT = process.env.NEXT_PUBLIC_SLICE_SUBJECT_ID || "01900000-0000-7000-8000-000000000010";
const TENANT = process.env.NEXT_PUBLIC_SLICE_TENANT_ID || "01900000-0000-7000-8000-000000000011";

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

type GqlResponse<T> = { data?: T; errors?: { message: string }[] };

async function gql<T>(query: string, variables?: Record<string, unknown>): Promise<T> {
  const res = await fetch(`${BFF_URL}/graphql`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-subject-id": SUBJECT,
      "x-tenant-id": TENANT,
    },
    body: JSON.stringify({ query, variables }),
  });
  if (!res.ok) {
    throw new Error(`BFF HTTP ${res.status}`);
  }
  const body = (await res.json()) as GqlResponse<T>;
  if (body.errors?.length) {
    throw new Error(body.errors.map((e) => e.message).join("; "));
  }
  if (!body.data) {
    throw new Error("BFF returned empty data");
  }
  return body.data;
}

function mapTask(raw: {
  id: string;
  title: string;
  objective: string;
  state: string;
  repositoryId: string;
  repositoryName: string;
  createdAt: string;
  paused: boolean;
}): TaskSummary {
  return {
    id: raw.id,
    title: raw.title,
    objective: raw.objective,
    state: raw.state as TaskState,
    repositoryId: raw.repositoryId,
    repositoryName: raw.repositoryName,
    createdAt: raw.createdAt,
    paused: raw.paused,
  };
}

const mockApi = {
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

const liveApi = {
  async listTasks(): Promise<TaskSummary[]> {
    const data = await gql<{
      tasks: {
        id: string;
        title: string;
        objective: string;
        state: string;
        repositoryId: string;
        repositoryName: string;
        createdAt: string;
        paused: boolean;
      }[];
    }>(`query { tasks { id title objective state repositoryId repositoryName createdAt paused } }`);
    return data.tasks.map(mapTask);
  },

  async getTask(id: string): Promise<TaskSummary | null> {
    const data = await gql<{
      task: {
        id: string;
        title: string;
        objective: string;
        state: string;
        repositoryId: string;
        repositoryName: string;
        createdAt: string;
        paused: boolean;
      } | null;
    }>(
      `query ($id: UUID!) { task(id: $id) { id title objective state repositoryId repositoryName createdAt paused } }`,
      { id },
    );
    return data.task ? mapTask(data.task) : null;
  },

  async listEvents(taskId: string): Promise<TaskEvent[]> {
    const data = await gql<{
      taskEvents: {
        id: string;
        sequence: number;
        eventType: string;
        actorType: string;
        summary: string;
        createdAt: string;
      }[];
    }>(
      `query ($taskId: UUID!) { taskEvents(taskId: $taskId) { id sequence eventType actorType summary createdAt } }`,
      { taskId },
    );
    return data.taskEvents;
  },

  async listApprovals(taskId: string): Promise<Approval[]> {
    const data = await gql<{
      taskApprovals: { id: string; gate: string; status: string; reason?: string }[];
    }>(
      `query ($taskId: UUID!) { taskApprovals(taskId: $taskId) { id gate status reason } }`,
      { taskId },
    );
    return data.taskApprovals.map((a) => ({
      id: a.id,
      gate: a.gate,
      status: a.status as Approval["status"],
      reason: a.reason,
    }));
  },

  async decideApproval(taskId: string, approvalId: string, decision: "approved" | "rejected") {
    const data = await gql<{
      decideApproval: { id: string; gate: string; status: string; reason?: string };
    }>(
      `mutation ($taskId: UUID!, $approvalId: UUID!, $decision: String!) {
        decideApproval(taskId: $taskId, approvalId: $approvalId, decision: $decision) {
          id gate status reason
        }
      }`,
      { taskId, approvalId, decision },
    );
    return {
      id: data.decideApproval.id,
      gate: data.decideApproval.gate,
      status: data.decideApproval.status as Approval["status"],
      reason: data.decideApproval.reason,
    };
  },

  async listRepos(): Promise<RepoStatus[]> {
    const data = await gql<{
      repositories: {
        id: string;
        fullName: string;
        indexState: string;
        lastSyncedAt: string;
      }[];
    }>(`query { repositories { id fullName indexState lastSyncedAt } }`);
    return data.repositories.map((r) => ({
      id: r.id,
      fullName: r.fullName,
      indexState: r.indexState as RepoStatus["indexState"],
      lastSyncedAt: r.lastSyncedAt,
    }));
  },

  async getUsage(): Promise<UsageSnapshot> {
    const data = await gql<{
      usage: {
        tokensUsed: number;
        tokensBudget: number;
        usdMicrosUsed: number;
        usdMicrosBudget: number;
      };
    }>(`query { usage { tokensUsed tokensBudget usdMicrosUsed usdMicrosBudget } }`);
    return data.usage;
  },

  async listChat(): Promise<ChatMessage[]> {
    const data = await gql<{
      chatMessages: {
        id: string;
        role: string;
        content: string;
        createdAt: string;
        taskId?: string;
      }[];
    }>(`query { chatMessages { id role content createdAt taskId } }`);
    return data.chatMessages.map((m) => ({
      id: m.id,
      role: m.role as ChatMessage["role"],
      content: m.content,
      createdAt: m.createdAt,
      taskId: m.taskId,
    }));
  },

  async sendChat(objective: string): Promise<{ messages: ChatMessage[]; task: TaskSummary }> {
    const data = await gql<{
      sendChat: {
        messages: {
          id: string;
          role: string;
          content: string;
          createdAt: string;
          taskId?: string;
        }[];
        task: {
          id: string;
          title: string;
          objective: string;
          state: string;
          repositoryId: string;
          repositoryName: string;
          createdAt: string;
          paused: boolean;
        } | null;
      };
    }>(
      `mutation ($content: String!) {
        sendChat(content: $content) {
          messages { id role content createdAt taskId }
          task { id title objective state repositoryId repositoryName createdAt paused }
        }
      }`,
      { content: objective },
    );
    const messages = data.sendChat.messages.map((m) => ({
      id: m.id,
      role: m.role as ChatMessage["role"],
      content: m.content,
      createdAt: m.createdAt,
      taskId: m.taskId,
    }));
    if (!data.sendChat.task) {
      throw new Error("sendChat did not return a task");
    }
    return { messages, task: mapTask(data.sendChat.task) };
  },
};

export const api = BFF_URL ? liveApi : mockApi;
