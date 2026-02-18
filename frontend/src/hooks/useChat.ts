'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import type { Message, Source, TrustScore, CostInfo } from '@/types'
import { apiClient } from '@/lib/api'
import { generateId } from '@/lib/utils'

interface UseChatReturn {
  messages: Message[]
  isLoading: boolean
  isStreaming: boolean
  error: string | null
  sendMessage: (query: string, mode?: 'normal' | 'agentic' | 'auto') => Promise<void>
  streamChat: (query: string, mode?: 'normal' | 'agentic' | 'auto') => Promise<void>
  clearMessages: () => void
  conversationId: string | null
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  setConversationId: React.Dispatch<React.SetStateAction<string | null>>
}

/**
 * Custom hook for managing chat state and interactions
 */
export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (query: string, mode: 'normal' | 'agentic' | 'auto' = 'normal') => {
      if (!query.trim()) return

      setIsLoading(true)
      setError(null)

      // Add user message
      const userMessage: Message = {
        id: generateId(),
        role: 'user',
        content: query,
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, userMessage])

      try {
        const response = await apiClient.chat({
          query,
          conversation_id: conversationId || undefined,
          mode,
        })

        // Update conversation ID if provided
        if (response.conversation_id) {
          setConversationId(response.conversation_id)
        }

        // Add assistant message
        const assistantMessage: Message = {
          id: generateId(),
          role: 'assistant',
          content: response.answer,
          sources: response.sources.map((source) => ({
            id: `${source.document_id}-${source.chunk_index}`,
            content: '',
            metadata: {
              source_file: source.filename,
              chunk_index: source.chunk_index,
              document_id: source.document_id,
              filename: source.filename,
            },
            score: source.score,
          })),
          timestamp: new Date(),
          trust: response.trust,
          cost: response.cost,
          mode_used: response.mode_used as 'normal' | 'agentic',
          reasoning_steps: response.reasoning_steps,
          classification: response.classification,
          sub_queries: response.sub_queries,
        }

        setMessages((prev) => [...prev, assistantMessage])
    } catch (err: any) {
      // Handle rate limit error specifically
      if (err?.status === 429 || err?.response?.status === 429) {
        const errorDetail = err?.detail || err?.response?.data?.detail || 'Rate limit exceeded'
        const errorMsg: Message = {
          id: generateId(),
          role: 'assistant',
          content: `⚠️ ${errorDetail}`,
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, errorMsg])
        setError(errorDetail)
      } else {
        const errorMessage = err instanceof Error ? err.message : 'Failed to send message'
        setError(errorMessage)
        
        // Add error message
        const errorMsg: Message = {
          id: generateId(),
          role: 'assistant',
          content: `Error: ${errorMessage}`,
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, errorMsg])
      }
    } finally {
      setIsLoading(false)
    }
  },
    [conversationId]
  )

  const streamChat = useCallback(
    async (query: string, mode: 'normal' | 'agentic' | 'auto' = 'normal') => {
      if (!query.trim() || isStreaming) return

      setIsStreaming(true)
      setError(null)

      // Add user message
      const userMessage: Message = {
        id: generateId(),
        role: 'user',
        content: query,
        timestamp: new Date(),
      }

      // Add placeholder assistant message
      const assistantId = generateId()
      const assistantMessage: Message = {
        id: assistantId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        sources: [],
      }

      setMessages((prev) => [...prev, userMessage, assistantMessage])

      try {
        const token = localStorage.getItem('auth_token')
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/chat/stream`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              query,
              conversation_id: conversationId,
              mode,
            }),
          }
        )

        if (!response.ok) throw new Error('Stream request failed')

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()

        if (!reader) throw new Error('No reader available')

        let buffer = ''
        let currentContent = ''
        let currentSources: Source[] = []
        let currentTrust: TrustScore | undefined = undefined
        let currentCost: CostInfo | undefined = undefined

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const rawLine of lines) {
            const line = rawLine.trim()
            if (!line) continue

            if (line.startsWith('event:')) {
              continue
            }
            if (line.startsWith('data:')) {
              const data = line.slice(5).trim()
              if (!data) continue

              try {
                const parsed = JSON.parse(data)

                if (parsed.content) {
                  // Token event - append content
                  currentContent += parsed.content
                  setMessages((prev) =>
                    prev.map((m) => (m.id === assistantId ? { ...m, content: currentContent } : m))
                  )
                } else if (parsed.sources) {
                  // Sources event
                  currentSources = parsed.sources.map((source: any) => ({
                    id: `${source.document_id}-${source.chunk_index}`,
                    content: source.content || '',
                    metadata: {
                      source_file: source.filename,
                      chunk_index: source.chunk_index,
                      document_id: source.document_id,
                      filename: source.filename,
                    },
                    score: source.score,
                  }))
                  setMessages((prev) =>
                    prev.map((m) => (m.id === assistantId ? { ...m, sources: currentSources } : m))
                  )
                } else if (parsed.grounding_score !== undefined) {
                  // Trust event
                  currentTrust = parsed as TrustScore
                  setMessages((prev) =>
                    prev.map((m) => (m.id === assistantId ? { ...m, trust: currentTrust } : m))
                  )
                } else if (parsed.total_tokens !== undefined || parsed.estimated_cost_usd !== undefined) {
                  // Cost event
                  currentCost = parsed as CostInfo
                  setMessages((prev) =>
                    prev.map((m) => (m.id === assistantId ? { ...m, cost: currentCost } : m))
                  )
                } else if (parsed.status === 'complete' || parsed.status === 'error') {
                  // Done event
                  break
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', e)
              }
            }
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Streaming failed')
        setMessages((prev) => prev.filter((m) => m.id !== assistantId))
      } finally {
        setIsStreaming(false)
      }
    },
    [conversationId, isStreaming]
  )

  // Note: localStorage persistence is handled in page.tsx to avoid hydration errors

  const clearMessages = useCallback(() => {
    setMessages([])
    setConversationId(null)
    setError(null)
    // Clear localStorage
    if (typeof window !== 'undefined') {
      localStorage.removeItem('chat_messages')
      localStorage.removeItem('conversation_id')
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }, [])

  return {
    messages,
    isLoading,
    isStreaming,
    error,
    sendMessage,
    streamChat,
    clearMessages,
    conversationId,
    setMessages,
    setConversationId,
  }
}
