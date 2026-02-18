'use client'

import React, { useState, useRef, useEffect } from 'react'
import { Zap, Brain, Sparkles, ChevronDown, Check } from 'lucide-react'

interface ModeSelectorProps {
  mode: 'normal' | 'agentic' | 'auto'
  onChange: (mode: 'normal' | 'agentic' | 'auto') => void
  disabled?: boolean
}

export function ModeSelector({ mode, onChange, disabled }: ModeSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const modes = [
    {
      id: 'normal' as const,
      label: 'Normal RAG',
      icon: Zap,
      description: 'Single retrieval, direct answer',
      color: 'text-emerald-600 dark:text-emerald-400',
      bgColor: 'bg-emerald-100 dark:bg-emerald-900/30',
    },
    {
      id: 'agentic' as const,
      label: 'Agentic RAG',
      icon: Brain,
      description: 'Multi-step reasoning & retrieval',
      color: 'text-purple-600 dark:text-purple-400',
      bgColor: 'bg-purple-100 dark:bg-purple-900/30',
    },
    {
      id: 'auto' as const,
      label: 'Auto',
      icon: Sparkles,
      description: 'Agent decides based on query',
      color: 'text-blue-600 dark:text-blue-400',
      bgColor: 'bg-blue-100 dark:bg-blue-900/30',
    },
  ]

  const currentMode = modes.find((m) => m.id === mode) || modes[0]
  const Icon = currentMode.icon

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={`
          flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium
          border border-slate-200 dark:border-slate-700
          bg-white dark:bg-slate-800
          hover:bg-slate-50 dark:hover:bg-slate-700
          disabled:opacity-50 disabled:cursor-not-allowed
          transition-colors
        `}
      >
        <Icon className={`h-3.5 w-3.5 ${currentMode.color}`} />
        <span className="text-slate-700 dark:text-slate-300">
          {currentMode.label}
        </span>
        <ChevronDown
          className={`h-3.5 w-3.5 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Dropdown menu */}
      {isOpen && (
        <div className="absolute bottom-full mb-2 left-0 w-48 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-lg z-50 overflow-hidden">
          <div className="p-1.5">
            {modes.map((m) => {
              const ModeIcon = m.icon
              const isSelected = mode === m.id
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    onChange(m.id)
                    setIsOpen(false)
                  }}
                  className={`
                    w-full flex items-start gap-2.5 p-2 rounded-md text-left
                    hover:bg-slate-100 dark:hover:bg-slate-700
                    transition-colors
                    ${isSelected ? 'bg-slate-100 dark:bg-slate-700' : ''}
                  `}
                >
                  <div className={`p-1 rounded ${m.bgColor}`}>
                    <ModeIcon className={`h-3.5 w-3.5 ${m.color}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                        {m.label}
                      </span>
                      {isSelected && (
                        <Check className="h-3.5 w-3.5 text-emerald-500" />
                      )}
                    </div>
                    <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
                      {m.description}
                    </p>
                  </div>
                </button>
              )
            })}
          </div>

          {/* Info footer */}
          <div className="px-3 py-2 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50">
            <p className="text-[10px] text-slate-500 dark:text-slate-400">
              Agentic RAG uses multi-step reasoning for complex queries. Costs
              ~3-5x more tokens.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default ModeSelector
