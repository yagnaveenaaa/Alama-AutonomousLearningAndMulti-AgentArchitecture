"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import { ui } from "@/shared/ui/PageShell";

export function UsageWidget() {
  const { data, isLoading } = useQuery({
    queryKey: ["usage"],
    queryFn: () => api.getUsage(),
  });

  if (isLoading || !data) {
    return <p className={ui.empty}>Loading budget…</p>;
  }

  const tokenPct = Math.min(100, Math.round((data.tokensUsed / data.tokensBudget) * 100));
  const usdUsed = (data.usdMicrosUsed / 1_000_000).toFixed(2);
  const usdBudget = (data.usdMicrosBudget / 1_000_000).toFixed(2);

  return (
    <div>
      <div className={ui.row}>
        <div>
          <strong>Token budget</strong>
          <div className={ui.meta}>
            {data.tokensUsed.toLocaleString()} / {data.tokensBudget.toLocaleString()}
          </div>
          <div className={ui.meter} aria-hidden>
            <span style={{ width: `${tokenPct}%` }} />
          </div>
        </div>
        <span className={ui.state}>{tokenPct}%</span>
      </div>
      <div className={ui.row}>
        <div>
          <strong>Spend</strong>
          <div className={ui.meta}>
            ${usdUsed} of ${usdBudget}
          </div>
        </div>
      </div>
    </div>
  );
}
