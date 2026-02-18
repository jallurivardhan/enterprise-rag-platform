'use client'

import React, { useState } from 'react'
import { ReasoningStep } from '@/types'
import {
  Brain,
  Search,
  FileText,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Target,
  Lightbulb,
} from 'lucide-react'

interface ReasoningStepsProps {
  steps: ReasoningStep[]
  subQueries?: string[]
}

export function ReasoningSteps({ steps, subQueries }: ReasoningStepsProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  // Get icon based on action type
  const getActionIcon = (action: string) => {
    switch (action) {
      case 'analyze':
        return <Brain className="h-3.5 w-3.5 text-purple-500" />
      case 'decompose':
        return <Target className="h-3.5 w-3.5 text-blue-500" />
      case 'retrieve':
        return <Search className="h-3.5 w-3.5 text-amber-500" />
      case 'synthesize':
        return <FileText className="h-3.5 w-3.5 text-green-500" />
      case 'verify':
        return <CheckCircle className="h-3.5 w-3.5 text-teal-500" />
      case 'complete':
        return <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
      default:
        return <Lightbulb className="h-3.5 w-3.5 text-slate-500" />
    }
  }

  // Get action label
  const getActionLabel = (action: string) => {
    switch (action) {
      case 'analyze':
        return 'Analyzing'
      case 'decompose':
        return 'Breaking down'
      case 'retrieve':
        return 'Retrieving'
      case 'synthesize':
        return 'Synthesizing'
      case 'verify':
        return 'Verifying'
      case 'complete':
        return 'Complete'
      default:
        return action
    }
  }

  const retrieveSteps = steps.filter((s) => s.action === 'retrieve')
  const totalChunks = retrieveSteps.reduce(
    (sum, s) => sum + (s.chunks_found || 0),
    0
  )

  return (
    <div className="mt-2 rounded-lg border border-indigo-300 bg-indigo-50 dark:border-indigo-800 dark:bg-indigo-950/30 overflow-hidden">
      {/* Header - Always visible */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-2.5 px-3 hover:bg-indigo-100/50 dark:hover:bg-indigo-900/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
          <span className="text-xs font-medium text-indigo-700 dark:text-indigo-300">
            Agentic Reasoning
          </span>
          <span className="text-xs text-indigo-600 dark:text-indigo-400">
            • {steps.length} steps • {retrieveSteps.length} retrievals •{' '}
            {totalChunks} chunks
          </span>
        </div>
        <div className="flex items-center gap-1 text-indigo-600 dark:text-indigo-400">
          <span className="text-[11px] uppercase tracking-wide">Details</span>
          {isExpanded ? (
            <ChevronUp className="h-3.5 w-3.5" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5" />
          )}
        </div>
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-3 pb-3 border-t border-indigo-300 dark:border-indigo-800">
          {/* Sub-queries used */}
          {subQueries && subQueries.length > 1 && (
            <div className="mt-3 mb-3 p-2 rounded-md bg-indigo-100 dark:bg-indigo-900/30">
              <div className="text-[11px] font-medium text-indigo-700 dark:text-indigo-400 mb-1.5">
                Query decomposed into:
              </div>
              <ul className="space-y-1">
                {subQueries.map((sq, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 text-xs text-indigo-800 dark:text-indigo-300"
                  >
                    <span className="text-indigo-400">{idx + 1}.</span>
                    <span>{sq}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Reasoning steps timeline */}
          <div className="mt-3 space-y-1">
            {steps.map((step, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 p-2 rounded-md hover:bg-indigo-100/30 dark:hover:bg-indigo-900/20 transition-colors"
              >
                {/* Step number and icon */}
                <div className="flex items-center gap-1.5 min-w-[60px]">
                  <span className="text-[10px] text-indigo-600 dark:text-indigo-500 font-mono">
                    #{step.step_number}
                  </span>
                  {getActionIcon(step.action)}
                </div>

                {/* Step content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-medium text-indigo-600 dark:text-indigo-400">
                      {getActionLabel(step.action)}
                    </span>
                    {step.chunks_found !== undefined && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                        {step.chunks_found} chunks
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-700 dark:text-slate-400 mt-0.5 line-clamp-2">
                    {step.thought}
                  </p>
                  {step.sub_query && (
                    <p className="text-[10px] text-indigo-600 dark:text-indigo-400 mt-1 italic">
                      Query: &quot;{step.sub_query}&quot;
                    </p>
                  )}
                  {step.result && (
                    <p className="text-[10px] text-green-700 dark:text-green-400 mt-1">
                      → {step.result}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default ReasoningSteps
