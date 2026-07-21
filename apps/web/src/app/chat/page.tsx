import { ChatPanel } from "@/features/chat/ChatPanel";
import { PageShell } from "@/shared/ui/PageShell";

export default function ChatPage() {
  return (
    <PageShell
      kicker="Chat"
      title="Describe the work"
      lede="Conversational entry creates a task, starts the agent workflow, and streams progress."
    >
      <ChatPanel />
    </PageShell>
  );
}
