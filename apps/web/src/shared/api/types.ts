export type TaskState =
  | "queued"
  | "importing"
  | "indexing"
  | "planning"
  | "executing"
  | "verifying"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "cancelled";

export type TaskSummary = {
  id: string;
  title: string;
  objective: string;
  state: TaskState;
  repositoryId: string;
  repositoryName: string;
  createdAt: string;
  paused: boolean;
};

export type TaskEvent = {
  id: string;
  sequence: number;
  eventType: string;
  actorType: string;
  summary: string;
  createdAt: string;
};

export type Approval = {
  id: string;
  gate: string;
  status: "pending" | "approved" | "rejected" | "expired";
  reason?: string;
};

export type RepoStatus = {
  id: string;
  fullName: string;
  indexState: "ready" | "indexing" | "failed" | "idle";
  lastSyncedAt: string;
};

export type UsageSnapshot = {
  tokensUsed: number;
  tokensBudget: number;
  usdMicrosUsed: number;
  usdMicrosBudget: number;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string;
  taskId?: string;
};
