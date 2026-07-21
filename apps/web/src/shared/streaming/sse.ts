/** SSE helpers — patch TanStack Query cache by sequence (LLD §10.5). */

export function shouldApplyEvent(currentSeq: number, incomingSeq: number): boolean {
  return incomingSeq > currentSeq;
}
