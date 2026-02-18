'use client'

import React, { useState } from 'react'
import { CostInfo } from '@/types'
import { Coins, ChevronDown, ChevronUp } from 'lucide-react'

interface CostIndicatorProps {
  cost: CostInfo
}

export const CostIndicator: React.FC<CostIndicatorProps> = ({ cost }) => {
  const [expanded, setExpanded] = useState(false)

  const totalTokens = cost.total_tokens ?? 0
  const inputTokens = cost.input_tokens ?? 0
  const outputTokens = cost.output_tokens ?? 0
  const costUsd = cost.estimated_cost_usd ?? 0
  const model = cost.model ?? 'gpt-4o-mini'

  const costFormatted =
    costUsd >= 0.01
      ? `$${costUsd.toFixed(2)}`
      : costUsd >= 0.0001
        ? `$${costUsd.toFixed(4)}`
        : `$${costUsd.toFixed(6)}`

  return (
    <div className="mt-1.5">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-100/80 px-2.5 py-1 text-[11px] text-slate-600 transition-colors hover:bg-slate-200/80 dark:border-slate-600 dark:bg-slate-800/60 dark:text-slate-400 dark:hover:bg-slate-700/60"
        aria-expanded={expanded}
        title="Token usage and cost"
      >
        <Coins className="h-3 w-3 shrink-0 opacity-70" />
        <span>
          {totalTokens.toLocaleString()} tokens · {costFormatted}
        </span>
        {expanded ? (
          <ChevronUp className="h-3 w-3 shrink-0" />
        ) : (
          <ChevronDown className="h-3 w-3 shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="mt-2 rounded-md border border-slate-200 bg-slate-50/80 px-2.5 py-2 text-[11px] text-slate-600 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            <span className="text-slate-500 dark:text-slate-500">Input tokens</span>
            <span className="font-medium tabular-nums">{inputTokens.toLocaleString()}</span>
            <span className="text-slate-500 dark:text-slate-500">Output tokens</span>
            <span className="font-medium tabular-nums">{outputTokens.toLocaleString()}</span>
            <span className="text-slate-500 dark:text-slate-500">Estimated cost</span>
            <span className="font-medium tabular-nums">{costFormatted}</span>
            <span className="text-slate-500 dark:text-slate-500">Model</span>
            <span className="font-medium truncate" title={model}>
              {model}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

export default CostIndicator
