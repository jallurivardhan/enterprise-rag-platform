'use client'

import React, { useState } from 'react'
import { TrustScore } from '@/types'
import {
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
} from 'lucide-react'

interface TrustIndicatorProps {
  trust: TrustScore
}

export const TrustIndicator: React.FC<TrustIndicatorProps> = ({ trust }) => {
  const [expanded, setExpanded] = useState(false)

  const confidence = trust.confidence ?? 0
  const confidencePercent = Math.round(confidence * 100)
  const groundingPercent = Math.round((trust.grounding_score ?? confidence) * 100)

  const hallucinationCheck =
    trust.check_results && typeof trust.check_results['hallucination'] === 'boolean'
      ? trust.check_results['hallucination']
      : true

  let level: 'high' | 'medium' | 'low' = 'low'
  if (confidence >= 0.8 && trust.is_grounded && hallucinationCheck) {
    level = 'high'
  } else if (confidence >= 0.5 && (trust.is_grounded || hallucinationCheck)) {
    level = 'medium'
  } else {
    level = 'low'
  }

  const levelLabel =
    level === 'high' ? 'High confidence' : level === 'medium' ? 'Medium confidence' : 'Low confidence'

  const levelColors =
    level === 'high'
      ? {
          badge: 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200',
          bar: 'bg-emerald-500',
        }
      : level === 'medium'
      ? {
          badge: 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-700 dark:bg-amber-900/40 dark:text-amber-200',
          bar: 'bg-amber-500',
        }
      : {
          badge: 'border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-700 dark:bg-rose-900/40 dark:text-rose-200',
          bar: 'bg-rose-500',
        }

  const LevelIcon = level === 'high' ? ShieldCheck : level === 'medium' ? ShieldAlert : ShieldX

  return (
    <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50/60 p-2 text-xs shadow-sm dark:border-slate-700 dark:bg-slate-900/40">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className={`flex w-full items-center justify-between gap-2 rounded-md border px-2 py-1 text-left transition-colors ${levelColors.badge}`}
        aria-expanded={expanded}
      >
        <span className="flex items-center gap-2">
          <LevelIcon className="h-4 w-4" />
          <span className="font-medium">{levelLabel}</span>
          <span className="text-xs opacity-80">
            {confidencePercent}% confidence • {trust.is_grounded ? 'Grounded in sources' : 'Weak grounding'}
          </span>
        </span>
        <span className="flex items-center gap-1 text-slate-600 dark:text-slate-300">
          <span className="text-[11px] uppercase tracking-wide">Details</span>
          {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </span>
      </button>

      {expanded && (
        <div className="mt-3 space-y-3 border-t border-slate-200 pt-3 dark:border-slate-700">
          {/* Grounding score */}
          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Grounding score
              </span>
              <span className="text-[11px] text-slate-600 dark:text-slate-300">{groundingPercent}%</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
              <div
                className={`h-full ${levelColors.bar} transition-all`}
                style={{ width: `${Math.min(100, Math.max(0, groundingPercent))}%` }}
              />
            </div>
          </div>

          {/* Check results */}
          {trust.check_results && Object.keys(trust.check_results).length > 0 && (
            <div>
              <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Checks
              </div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(trust.check_results).map(([key, passed]) => {
                  const label = key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                  return (
                    <div
                      key={key}
                      className="flex items-center gap-1.5 rounded-md bg-slate-100 px-2 py-1 dark:bg-slate-800/70"
                    >
                      {passed ? (
                        <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5 text-rose-500" />
                      )}
                      <span className="text-[11px] text-slate-700 dark:text-slate-200">{label}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Issues */}
          {trust.issues && trust.issues.length > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 px-2.5 py-2 text-[11px] text-amber-900 dark:border-amber-700 dark:bg-amber-900/40 dark:text-amber-100">
              <div className="mb-1 flex items-center gap-1.5 font-medium">
                <AlertTriangle className="h-3.5 w-3.5" />
                <span>Potential issues detected</span>
              </div>
              <ul className="ml-4 list-disc space-y-0.5">
                {trust.issues.map((issue, idx) => (
                  <li key={idx}>{issue}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Info footer */}
          <div className="flex items-start gap-1.5 rounded-md bg-slate-100 px-2.5 py-2 text-[11px] text-slate-600 dark:bg-slate-800/70 dark:text-slate-300">
            <Info className="mt-[1px] h-3.5 w-3.5 shrink-0" />
            <p>
              Trust scores estimate how well this answer is grounded in your documents and passes automatic safety checks.
              Always verify critical information with your own judgement.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default TrustIndicator

