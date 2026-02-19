'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useChat } from '@/hooks/useChat'
import { apiClient } from '@/lib/api'
import { Document, Message } from '@/types'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Upload, FileText, Trash2, Send, Menu, X, Sun, Moon, ChevronDown, ChevronUp, RotateCcw, ThumbsUp, ThumbsDown, BarChart3, LogOut, Shield, Brain, Mic, MicOff, Zap, FileDown, Keyboard, Lightbulb } from 'lucide-react'
import Link from 'next/link'
import { formatDate, generateId } from '@/lib/utils'
import { toast } from '@/hooks/use-toast'
import { getToken, getUser, logout, authFetch } from '@/lib/auth'
import { TrustIndicator } from '@/components/TrustIndicator'
import { CostIndicator } from '@/components/CostIndicator'
import { ModeSelector } from '@/components/ModeSelector'
import { ReasoningSteps } from '@/components/ReasoningSteps'
import { useVoiceInput } from '@/hooks/useVoiceInput'

export default function Home() {
  const router = useRouter()
  const { messages, isLoading, isStreaming, sendMessage, streamChat, clearMessages, conversationId, setMessages, setConversationId } = useChat()
  const [documents, setDocuments] = useState<Document[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [isDark, setIsDark] = useState(true)
  const [isThemeTransitioning, setIsThemeTransitioning] = useState(false)
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set())
  const [messageFeedback, setMessageFeedback] = useState<Map<string, 'up' | 'down'>>(new Map())
  const [user, setUser] = useState<any>(null)
  const [rateLimit, setRateLimit] = useState<{limit: number, remaining: number} | null>(null)
  const [useStreaming, setUseStreaming] = useState(true)
  const [ragMode, setRagMode] = useState<'normal' | 'agentic' | 'auto'>('normal')
  const [compareMode, setCompareMode] = useState(false)
  const [compareResults, setCompareResults] = useState<{ normal: Message | null; agentic: Message | null }>({ normal: null, agentic: null })
  const [isComparing, setIsComparing] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const templatesRef = useRef<HTMLDivElement>(null)

  const promptTemplates = [
    { icon: '📊', title: 'Compare Projects', prompt: 'Compare the technologies and approaches used in different projects', category: 'Analysis' },
    { icon: '📝', title: 'Summarize Document', prompt: 'Provide a comprehensive summary of the key points in my documents', category: 'Summary' },
    { icon: '🔍', title: 'Find Specific Info', prompt: 'What information do the documents contain about', category: 'Search' },
    { icon: '💡', title: 'Explain Concept', prompt: 'Explain the concept of', category: 'Learning' },
    { icon: '📋', title: 'List Key Points', prompt: 'List the main points and takeaways from the documents about', category: 'Summary' },
    { icon: '🤔', title: 'Analyze & Recommend', prompt: 'Analyze the following and provide recommendations:', category: 'Analysis' },
    { icon: '⚖️', title: 'Pros and Cons', prompt: 'What are the pros and cons of', category: 'Analysis' },
    { icon: '📈', title: 'Technical Details', prompt: 'Explain the technical implementation details of', category: 'Technical' }
  ]
  const { isListening, transcript, startListening, stopListening, isSupported } = useVoiceInput()

  useEffect(() => {
    if (transcript) {
      setInputValue(transcript)
    }
  }, [transcript])

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (templatesRef.current && !templatesRef.current.contains(e.target as Node)) {
        setShowTemplates(false)
      }
    }
    if (showTemplates) {
      document.addEventListener('click', handleClickOutside)
      return () => document.removeEventListener('click', handleClickOutside)
    }
  }, [showTemplates])

  // Check authentication and initialize
  useEffect(() => {
    // Check auth
    const token = getToken()
    const userData = getUser()
    
    if (!token || !userData) {
      router.push('/login')
      return
    }
    
    setUser(userData)
    
    // Prevent theme flash - read from localStorage before render
    const savedTheme = localStorage.getItem('theme')
    if (savedTheme) {
      const dark = savedTheme === 'dark'
      setIsDark(dark)
      document.documentElement.classList.toggle('dark', dark)
    } else {
      // Default to dark mode
      document.documentElement.classList.add('dark')
    }
    setMounted(true)
  }, [router])

  // Toggle theme with overlay fade - MUST be before early return
  const handleThemeToggle = useCallback(() => {
    setIsThemeTransitioning(true)
    setTimeout(() => {
      const newTheme = !isDark
      setIsDark(newTheme)
      document.documentElement.classList.toggle('dark', newTheme)
      localStorage.setItem('theme', newTheme ? 'dark' : 'light')
      setTimeout(() => {
        setIsThemeTransitioning(false)
      }, 150)
    }, 150)
  }, [isDark])

  // Fetch documents - MUST be defined before useEffect that uses it
  const fetchDocuments = useCallback(async () => {
    const token = localStorage.getItem('auth_token')
    
    if (!token) {
      console.log('No auth token found')
      return
    }
    
    try {
      const response = await fetch('https://enterprise-rag-platform.onrender.com/api/ingest/documents', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (response.status === 401) {
        // Token expired or invalid, redirect to login
        localStorage.removeItem('auth_token')
        localStorage.removeItem('user')
        window.location.href = '/login'
        return
      }
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      setDocuments(data.documents || [])
    } catch (error) {
      console.error('Failed to fetch documents:', error)
      toast({
        title: 'Error',
        description: 'Failed to load documents',
        variant: 'destructive',
      })
    }
  }, [])

  // Fetch rate limit status - MUST be defined before useEffect that uses it
  const fetchRateLimit = useCallback(async () => {
    const token = localStorage.getItem('auth_token')
    if (!token) return
    
    try {
      const status = await apiClient.getRateLimitStatus()
      setRateLimit({ limit: status.limit, remaining: status.remaining })
    } catch (error) {
      console.error('Failed to fetch rate limit:', error)
    }
  }, [])

  // Load saved messages after mount (prevents hydration error)
  useEffect(() => {
    if (!mounted) return
    
    // Load saved messages after mount
    const savedMessages = localStorage.getItem('chat_messages')
    const savedConvId = localStorage.getItem('conversation_id')
    
    if (savedMessages) {
      try {
        const parsed = JSON.parse(savedMessages)
        // Convert timestamp strings back to Date objects
        const messagesWithDates = parsed.map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp)
        }))
        setMessages(messagesWithDates)
      } catch (e) {
        console.error('Failed to parse saved messages:', e)
      }
    }
    if (savedConvId) {
      setConversationId(savedConvId)
    }
  }, [mounted, setMessages, setConversationId])

  // Fetch documents on mount - MUST be after fetchDocuments and fetchRateLimit are defined
  useEffect(() => {
    if (mounted) {
      fetchDocuments()
      fetchRateLimit()
    }
  }, [mounted, fetchDocuments, fetchRateLimit])

  // Save messages to localStorage only when mounted
  useEffect(() => {
    if (!mounted) return
    
    if (messages.length > 0) {
      localStorage.setItem('chat_messages', JSON.stringify(messages))
    }
    if (conversationId) {
      localStorage.setItem('conversation_id', conversationId)
    }
  }, [messages, conversationId, mounted])

  const handleCompare = async (query: string) => {
    if (!query.trim()) return
    setIsComparing(true)
    setCompareResults({ normal: null, agentic: null })

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'https://enterprise-rag-platform.onrender.com'
      const token = localStorage.getItem('auth_token')
      const headers: HeadersInit = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const [normalRes, agenticRes] = await Promise.all([
        fetch(`${baseUrl}/api/chat`, { method: 'POST', headers, body: JSON.stringify({ query, mode: 'normal' }) }).then((r) => r.json()),
        fetch(`${baseUrl}/api/chat`, { method: 'POST', headers, body: JSON.stringify({ query, mode: 'agentic' }) }).then((r) => r.json())
      ])

      setCompareResults({
        normal: {
          id: 'normal',
          role: 'assistant',
          content: normalRes.answer ?? '',
          timestamp: new Date(),
          trust: normalRes.trust,
          cost: normalRes.cost,
          sources: normalRes.sources
        },
        agentic: {
          id: 'agentic',
          role: 'assistant',
          content: agenticRes.answer ?? '',
          timestamp: new Date(),
          trust: agenticRes.trust,
          cost: agenticRes.cost,
          sources: agenticRes.sources,
          reasoning_steps: agenticRes.reasoning_steps,
          sub_queries: agenticRes.sub_queries
        }
      })
    } catch (err) {
      console.error('Compare failed:', err)
    } finally {
      setIsComparing(false)
    }
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim() || isLoading || isStreaming) return

    const query = inputValue.trim()
    setInputValue('')
    if (compareMode) {
      await handleCompare(query)
    } else if (useStreaming) {
      await streamChat(query, ragMode)
    } else {
      await sendMessage(query, ragMode)
    }
    // Fetch rate limit status after sending message
    fetchRateLimit()
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    const validTypes = ['.pdf', '.docx', '.txt']
    const fileExt = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!validTypes.includes(fileExt)) {
      toast({
        title: 'Invalid file type',
        description: 'Please upload a PDF, DOCX, or TXT file',
        variant: 'destructive',
      })
      return
    }

    // Validate file size (10MB)
    if (file.size > 10 * 1024 * 1024) {
      toast({
        title: 'File too large',
        description: 'Maximum file size is 10MB',
        variant: 'destructive',
      })
      return
    }

    setIsUploading(true)
    try {
      const response = await apiClient.uploadDocument(file)
      toast({
        title: 'Upload successful',
        description: `Document "${response.filename || file.name}" has been processed.`,
      })
      await fetchDocuments()
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Upload failed'
      toast({
        title: 'Upload failed',
        description: errorMessage,
        variant: 'destructive',
      })
    } finally {
      setIsUploading(false)
      e.target.value = ''
    }
  }

  const handleDeleteDocument = async (documentId: string) => {
    if (!confirm('Are you sure you want to delete this document?')) return

    try {
      await apiClient.deleteDocument(documentId)
      toast({
        title: 'Document deleted',
        description: 'The document has been removed.',
      })
      await fetchDocuments()
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Delete failed'
      toast({
        title: 'Delete failed',
        description: errorMessage,
        variant: 'destructive',
      })
    }
  }

  const togglePermission = async (docId: string, currentPermission: string) => {
    const token = localStorage.getItem('auth_token')
    const newPermission = currentPermission === 'private' ? 'public' : 'private'
    
    try {
      const response = await fetch(
        `https://enterprise-rag-platform.onrender.com/api/ingest/documents/${docId}/permission`,
        {
          method: 'PATCH',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ permission: newPermission })
        }
      )
      
      if (response.ok) {
        fetchDocuments()
      }
    } catch (error) {
      console.error('Failed to update permission:', error)
    }
  }

  const clearChat = () => {
    clearMessages()
    setMessageFeedback(new Map()) // Clear feedback state
    // Clear localStorage
    localStorage.removeItem('chat_messages')
    localStorage.removeItem('conversation_id')
    toast({
      title: 'Chat cleared',
      description: 'All messages have been cleared.',
    })
  }

  const exportToPDF = () => {
    const printContent = document.createElement('div')
    printContent.innerHTML = `
      <html>
        <head>
          <title>Enterprise RAG - Chat Export</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 30px; border-bottom: 2px solid #4F46E5; padding-bottom: 20px; }
            .header h1 { color: #4F46E5; margin: 0; }
            .header p { color: #666; margin-top: 8px; }
            .message { margin: 20px 0; padding: 15px; border-radius: 10px; }
            .user { background: #4F46E5; color: white; margin-left: 20%; }
            .assistant { background: #F1F5F9; color: #1E293B; margin-right: 20%; }
            .meta { font-size: 12px; color: #666; margin-top: 10px; }
            .sources { font-size: 11px; color: #666; margin-top: 10px; padding-top: 10px; border-top: 1px solid #ddd; }
            .trust { font-size: 11px; padding: 5px 10px; border-radius: 5px; display: inline-block; margin-top: 10px; }
            .trust.high { background: #D1FAE5; color: #065F46; }
            .trust.medium { background: #FEF3C7; color: #92400E; }
            .trust.low { background: #FEE2E2; color: #991B1B; }
            .footer { margin-top: 40px; text-align: center; font-size: 12px; color: #999; }
          </style>
        </head>
        <body>
          <div class="header">
            <h1>Enterprise RAG Platform</h1>
            <p>Chat Export - ${new Date().toLocaleString()}</p>
          </div>
          ${messages.map(msg => `
            <div class="message ${msg.role}">
              <strong>${msg.role === 'user' ? 'You' : 'AI Assistant'}</strong>
              <p>${msg.content.replace(/\n/g, '<br>')}</p>
              ${msg.trust ? `<div class="trust ${msg.trust.hallucination_risk}">${Math.round(msg.trust.confidence * 100)}% confidence</div>` : ''}
              ${msg.sources && msg.sources.length > 0 ? `<div class="sources">Sources: ${msg.sources.map(s => s.metadata?.filename || 'Unknown').join(', ')}</div>` : ''}
              <div class="meta">${new Date(msg.timestamp).toLocaleString()}</div>
            </div>
          `).join('')}
          <div class="footer">
            Generated by Enterprise RAG Platform | ${messages.length} messages
          </div>
        </body>
      </html>
    `

    const printWindow = window.open('', '_blank')
    if (printWindow) {
      printWindow.document.write(printContent.innerHTML)
      printWindow.document.close()
      printWindow.print()
    }
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + Enter: Send message
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        if (inputValue.trim() && !isLoading && !isStreaming) {
          const form = document.querySelector('form')
          if (form) form.requestSubmit()
        }
      }

      // Ctrl/Cmd + K: Focus search/input
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        document.querySelector('textarea')?.focus()
      }

      // Ctrl/Cmd + L: Clear chat
      if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
        e.preventDefault()
        clearChat()
      }

      // Ctrl/Cmd + E: Export to PDF
      if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
        e.preventDefault()
        if (messages.length > 0) exportToPDF()
      }

      // Ctrl/Cmd + M: Toggle mode (Normal/Agentic/Auto)
      if ((e.ctrlKey || e.metaKey) && e.key === 'm') {
        e.preventDefault()
        setRagMode((prev) => (prev === 'normal' ? 'agentic' : prev === 'agentic' ? 'auto' : 'normal'))
      }

      // Ctrl/Cmd + D: Toggle dark mode
      if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
        e.preventDefault()
        handleThemeToggle()
      }

      // Escape: Close modals or stop listening
      if (e.key === 'Escape') {
        setShowShortcuts(false)
        if (isListening) stopListening()
      }

      // Ctrl/Cmd + /: Show shortcuts help
      if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault()
        setShowShortcuts((prev) => !prev)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [inputValue, isLoading, isStreaming, messages.length, ragMode, isDark, isListening])

  const toggleSourceExpansion = (messageId: string) => {
    setExpandedSources((prev) => {
      const next = new Set(prev)
      if (next.has(messageId)) {
        next.delete(messageId)
      } else {
        next.add(messageId)
      }
      return next
    })
  }

  const handleFeedback = async (message: Message, rating: 'up' | 'down') => {
    try {
      // Find the user question for this answer
      const messageIndex = messages.findIndex(m => m.id === message.id)
      const userQuestion = messageIndex > 0 && messages[messageIndex - 1]?.role === 'user' 
        ? messages[messageIndex - 1].content 
        : ''
      
      const response = await fetch('https://enterprise-rag-platform.onrender.com/api/chat/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userQuestion,
          answer: message.content,
          rating: rating,
          conversation_id: conversationId
        })
      })

      if (!response.ok) {
        throw new Error('Failed to submit feedback')
      }

      // Update local feedback state
      setMessageFeedback((prev) => {
        const next = new Map(prev)
        next.set(message.id, rating)
        return next
      })

      toast({
        title: 'Feedback submitted',
        description: `Thank you for your ${rating === 'up' ? 'positive' : 'negative'} feedback!`,
      })
    } catch (error) {
      console.error('Failed to submit feedback:', error)
      toast({
        title: 'Error',
        description: 'Failed to submit feedback. Please try again.',
        variant: 'destructive',
      })
    }
  }

  // Don't render until mounted to prevent hydration error
  if (!mounted) {
    return (
      <div className="min-h-screen bg-[#0f172a]">
        <div className="flex items-center justify-center h-screen">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-100 via-white to-indigo-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900 text-gray-900 dark:text-gray-100 transition-colors duration-200 relative">
      {/* Theme transition overlay */}
      <div
        className={`fixed inset-0 bg-white dark:bg-slate-900 pointer-events-none z-[9999] transition-opacity duration-300 ${
          isThemeTransitioning ? 'opacity-100' : 'opacity-0'
        }`}
      />
      {/* Dot pattern overlay */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgba(148,163,184,0.15)_1px,transparent_0)] dark:bg-[radial-gradient(circle_at_1px_1px,rgba(71,85,105,0.3)_1px,transparent_0)] bg-[length:24px_24px]" />
      </div>
      {/* Subtle mesh gradient overlay - light mode only */}
      <div className="fixed inset-0 pointer-events-none z-0 dark:hidden">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-200/40 rounded-full blur-3xl" />
        <div className="absolute top-1/3 right-1/4 w-80 h-80 bg-purple-200/30 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 left-1/3 w-72 h-72 bg-blue-200/30 rounded-full blur-3xl" />
      </div>
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? 'w-[300px] flex' : 'w-0 hidden'
        } md:flex md:w-[300px] bg-white/90 dark:bg-slate-900/90 backdrop-blur-sm border-r border-slate-200 dark:border-slate-700 flex-col transition-all duration-300 overflow-hidden relative z-10`}
      >
        <div className="p-4 border-b border-gray-200 dark:border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">Documents</h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSidebarOpen(false)}
              className="md:hidden text-gray-500 dark:text-slate-400 hover:text-gray-900 dark:hover:text-white"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={handleFileUpload}
            className="hidden"
            disabled={isUploading}
          />
          <Button
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
            disabled={isUploading}
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="h-4 w-4 mr-2" />
            {isUploading ? 'Uploading...' : 'Upload Document'}
          </Button>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-4 space-y-3">
            {documents.length === 0 ? (
              <div className="text-center py-12">
                <FileText className="h-12 w-12 mx-auto text-gray-400 dark:text-slate-500 mb-3" />
                <p className="text-sm text-gray-500 dark:text-slate-400">
                  No documents uploaded yet.
                </p>
              </div>
            ) : (
              documents.map((doc) => (
                <Card
                  key={doc.id}
                  className="p-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 shadow-sm hover:shadow-md transition-all duration-200 rounded-xl cursor-pointer"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <FileText className="h-4 w-4 text-indigo-600 dark:text-indigo-400 flex-shrink-0" />
                        <p className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
                          {doc.filename}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 mb-2">
                        <Badge
                          variant="secondary"
                          className="bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 text-xs font-medium"
                        >
                          {doc.chunks_count} chunks
                        </Badge>
                      </div>
                      <p className="text-xs text-gray-500 dark:text-slate-400">
                        {formatDate(doc.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {/* Permission Badge */}
                      <button
                        onClick={() => {
                          console.log('Button clicked for doc:', doc.id)
                          togglePermission(doc.id, doc.permission || 'public')
                        }}
                        className={`text-xs px-2 py-0.5 rounded-full cursor-pointer ${
                          doc.permission === 'private'
                            ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                            : 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                        }`}
                      >
                        {doc.permission === 'private' ? '🔒 Private' : '🌐 Public'}
                      </button>
                      {/* Delete button */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteDocument(doc.id)}
                        className="h-8 w-8 p-0 text-gray-400 dark:text-slate-400 hover:text-red-500 dark:hover:text-red-400 transition-all duration-200"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>
        </ScrollArea>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col relative z-10">
        {/* Decorative gradient orbs */}
        <div className="absolute top-20 right-20 w-72 h-72 bg-gradient-to-br from-indigo-400/20 to-purple-400/20 dark:from-indigo-600/10 dark:to-purple-600/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-20 left-20 w-96 h-96 bg-gradient-to-tr from-blue-400/20 to-cyan-400/20 dark:from-blue-600/10 dark:to-cyan-600/10 rounded-full blur-3xl pointer-events-none" />
        {/* Header */}
        <header className="relative bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-700 shadow-sm px-6 py-4 before:absolute before:inset-0 before:bg-gradient-to-r before:from-indigo-500/10 before:via-purple-500/10 before:to-pink-500/10 before:blur-3xl before:-z-10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="md:hidden text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700"
              >
                <Menu className="h-5 w-5" />
              </Button>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 tracking-tight">
                Enterprise RAG Platform
              </h1>
              {conversationId && (
                <span className="text-xs text-gray-500 dark:text-slate-400 bg-gray-100 dark:bg-slate-700 px-2 py-1 rounded">
                  Conversation Memory Active
                </span>
              )}
            </div>
            <div className="flex items-center gap-4">
              {/* Show current user */}
              {user && (
                <>
                  <span className={`text-sm ${isDark ? 'text-slate-400' : 'text-gray-600'}`}>
                    👤 {user.username}
                  </span>
                  {user.role === 'admin' && (
                    <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded-full">
                      Admin
                    </span>
                  )}
                </>
              )}
              
              {/* Admin link */}
              {user && user.role === 'admin' && (
                <Link 
                  href="/admin"
                  className="flex items-center gap-1 text-sm text-slate-400 hover:text-purple-400 transition-colors"
                >
                  <Shield className="w-4 h-4" />
                  Admin
                </Link>
              )}
              
              {/* Rate limit indicator */}
              {rateLimit && (
                <span className={`text-xs px-2 py-1 rounded-full ${
                  rateLimit.remaining < 5 ? 'bg-red-500/20 text-red-400' : 'bg-slate-700 text-slate-400'
                }`}>
                  {rateLimit.remaining}/{rateLimit.limit} requests
                </span>
              )}
              
              {/* Analytics link */}
              <Link 
                href="/analytics"
                className="flex items-center gap-1 text-sm text-slate-400 hover:text-indigo-400 transition-colors"
              >
                <BarChart3 className="w-4 h-4" />
                Analytics
              </Link>
              <button
                type="button"
                onClick={clearChat}
                disabled={messages.length === 0}
                className="flex items-center gap-1 text-sm text-gray-400 dark:text-gray-300 hover:text-gray-200 dark:hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed px-3 py-2 rounded-md hover:bg-gray-100 dark:hover:bg-slate-700"
              >
                <RotateCcw className="w-4 h-4" />
                Clear Chat
              </button>
              <button
                type="button"
                onClick={exportToPDF}
                disabled={messages.length === 0}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title="Export chat to PDF"
              >
                <FileDown className="h-4 w-4" />
                <span className="hidden sm:inline">Export</span>
              </button>
              {/* Logout button */}
              <button
                onClick={() => {
                  localStorage.removeItem('auth_token')
                  localStorage.removeItem('user')
                  localStorage.removeItem('chat_messages')
                  localStorage.removeItem('conversation_id')
                  window.location.href = '/login'
                }}
                className="flex items-center gap-1 text-sm text-slate-400 hover:text-red-400 transition-colors"
              >
                <LogOut className="w-4 h-4" />
                Logout
              </button>
              <button
                type="button"
                onClick={() => setShowShortcuts(true)}
                className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition-colors"
                title="Keyboard shortcuts (Ctrl+/)"
              >
                <Keyboard className="h-4 w-4" />
              </button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleThemeToggle}
                className="text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700 transition-all duration-200 rounded-full p-2"
                aria-label="Toggle theme"
              >
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
            </div>
          </div>
        </header>

        {/* Chat Messages */}
        <ScrollArea className="flex-1 p-6 bg-gradient-to-b from-white via-slate-50 to-slate-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900">
          <div className="max-w-4xl mx-auto space-y-4 relative">
            {compareMode && (compareResults.normal || compareResults.agentic || isComparing) && (
              <div className="grid grid-cols-2 gap-4 p-4">
                {/* Normal RAG Column */}
                <div className="border border-emerald-200 dark:border-emerald-800 rounded-xl p-4 bg-emerald-50/50 dark:bg-emerald-900/20">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-emerald-200 dark:border-emerald-800">
                    <Zap className="h-4 w-4 text-emerald-600" />
                    <span className="font-semibold text-emerald-700 dark:text-emerald-400">Normal RAG</span>
                  </div>
                  {isComparing ? (
                    <div className="animate-pulse text-slate-500">Processing...</div>
                  ) : compareResults.normal ? (
                    <div>
                      <p className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{compareResults.normal.content}</p>
                      {compareResults.normal.trust && <TrustIndicator trust={compareResults.normal.trust} />}
                      {compareResults.normal.cost && <CostIndicator cost={compareResults.normal.cost} />}
                    </div>
                  ) : null}
                </div>

                {/* Agentic RAG Column */}
                <div className="border border-purple-200 dark:border-purple-800 rounded-xl p-4 bg-purple-50/50 dark:bg-purple-900/20">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-purple-200 dark:border-purple-800">
                    <Brain className="h-4 w-4 text-purple-600" />
                    <span className="font-semibold text-purple-700 dark:text-purple-400">Agentic RAG</span>
                  </div>
                  {isComparing ? (
                    <div className="animate-pulse text-slate-500">Processing with reasoning...</div>
                  ) : compareResults.agentic ? (
                    <div>
                      <p className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{compareResults.agentic.content}</p>
                      {compareResults.agentic.reasoning_steps && (
                        <ReasoningSteps steps={compareResults.agentic.reasoning_steps} subQueries={compareResults.agentic.sub_queries} />
                      )}
                      {compareResults.agentic.trust && <TrustIndicator trust={compareResults.agentic.trust} />}
                      {compareResults.agentic.cost && <CostIndicator cost={compareResults.agentic.cost} />}
                    </div>
                  ) : null}
                </div>
              </div>
            )}
            {isStreaming && (
              <div className="flex items-center gap-2 text-sm text-indigo-500 dark:text-indigo-400">
                <span className="animate-pulse">●</span>
                <span>Streaming response...</span>
              </div>
            )}
            {messages.length === 0 ? (
              <div className="flex items-center justify-center h-full min-h-[400px]">
                <div className="text-center">
                  <div className="mb-4">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-indigo-100 dark:bg-indigo-900/30 mb-4">
                      <FileText className="h-8 w-8 text-indigo-600 dark:text-indigo-400" />
                    </div>
                  </div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
                    Start a conversation
                  </h2>
                  <p className="text-gray-500 dark:text-slate-400 text-lg">
                    Ask a question or upload a document to get started.
                  </p>
                </div>
              </div>
            ) : (
              messages.map((message, index) => (
                <div
                  key={message.id}
                  className={`flex gap-4 ${
                    message.role === 'user' ? 'flex-row-reverse' : 'flex-row'
                  }`}
                >
                  <Avatar className="h-10 w-10 border-2 border-gray-200 dark:border-slate-700">
                    <AvatarFallback
                      className={
                        message.role === 'user'
                          ? 'bg-indigo-600 text-white font-semibold'
                          : 'bg-gray-100 dark:bg-[#334155] text-gray-700 dark:text-gray-300 font-semibold'
                      }
                    >
                      {message.role === 'user' ? 'U' : 'AI'}
                    </AvatarFallback>
                  </Avatar>

                  <div
                    className={`flex flex-col gap-2 ${
                      message.role === 'user' ? 'items-end' : 'items-start'
                    } flex-1 max-w-[85%]`}
                  >
                    <div
                      className={`p-4 rounded-2xl ${
                        message.role === 'user'
                          ? 'bg-indigo-600 text-white'
                          : 'bg-white dark:bg-slate-800 text-gray-900 dark:text-gray-100 shadow-sm hover:shadow-md transition-shadow duration-200 border border-slate-200 dark:border-slate-700'
                      }`}
                    >
                      <p className="whitespace-pre-wrap break-words text-base leading-relaxed">
                        {message.content}
                      </p>
                      {/* Mode indicator for smart/auto responses */}
                      {message.role !== 'user' && message.mode_used === 'agentic' && (
                        <div className="flex items-center gap-2 mt-2 text-xs text-purple-600 dark:text-purple-400">
                          <Brain className="h-3.5 w-3.5" />
                          <span>Answered using Agentic RAG (multi-step reasoning)</span>
                        </div>
                      )}
                      {message.role !== 'user' && message.classification && (
                        <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-1">
                          Auto-detected as {message.classification.complexity} query ({Math.round(message.classification.confidence * 100)}% confidence)
                        </div>
                      )}
                      {/* Reasoning Steps - Only for agentic (smart) mode responses */}
                      {message.role !== 'user' && message.reasoning_steps && message.reasoning_steps.length > 0 && (
                        <ReasoningSteps
                          steps={message.reasoning_steps}
                          subQueries={message.sub_queries}
                        />
                      )}
                      {/* Trust Indicator - Only for AI responses with trust data */}
                      {message.role !== 'user' && message.trust && (
                        <TrustIndicator trust={message.trust} />
                      )}
                      {/* Cost Indicator */}
                      {message.role !== 'user' && message.cost && (
                        <CostIndicator cost={message.cost} />
                      )}
                      {message.sources && message.sources.length > 0 && (
                        <div className="mt-4 pt-4 border-t border-slate-300 dark:border-slate-500">
                          <button
                            onClick={() => toggleSourceExpansion(message.id)}
                            className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white mb-2 transition-colors"
                          >
                            <span className="text-slate-700 dark:text-slate-300">Sources</span>
                            <span className="text-slate-600 dark:text-slate-400">({message.sources.length})</span>
                            {expandedSources.has(message.id) ? (
                              <ChevronUp className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                            ) : (
                              <ChevronDown className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                            )}
                          </button>
                          {expandedSources.has(message.id) && (
                            <div className="space-y-2">
                              {message.sources.map((source, idx) => {
                                const filename =
                                  source.metadata.filename ||
                                  source.metadata.source_file ||
                                  'Unknown'
                                const pageOrChunk = source.metadata.page_number
                                  ? `Page ${source.metadata.page_number}`
                                  : `Chunk ${(source.metadata.chunk_index ?? 0) + 1}`
                                const scorePercent = (source.score * 100).toFixed(0)

                                return (
                                  <div
                                    key={source.id || idx}
                                    className="text-sm bg-slate-200/50 dark:bg-slate-600/50 p-3 rounded-lg border border-slate-300 dark:border-slate-500/50"
                                  >
                                    <p className="font-medium text-slate-800 dark:text-gray-100">
                                      {filename} - {pageOrChunk} ({scorePercent}%)
                                    </p>
                                  </div>
                                )
                              })}
                            </div>
                          )}
                        </div>
                      )}
                      {message.role === 'assistant' && (
                        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-300 dark:border-slate-500/50">
                          <span className="text-xs text-slate-600 dark:text-slate-400">Was this helpful?</span>
                          <button
                            onClick={() => handleFeedback(message, 'up')}
                            className={`p-1.5 rounded-lg transition-colors ${
                              messageFeedback.get(message.id) === 'up'
                                ? 'bg-green-500/20 text-green-600 dark:text-green-400'
                                : 'hover:bg-slate-200/50 dark:hover:bg-slate-600/50 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:text-green-500 dark:hover:text-green-400'
                            }`}
                            aria-label="Thumbs up"
                          >
                            <ThumbsUp className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleFeedback(message, 'down')}
                            className={`p-1.5 rounded-lg transition-colors ${
                              messageFeedback.get(message.id) === 'down'
                                ? 'bg-red-500/20 text-red-600 dark:text-red-400'
                                : 'hover:bg-slate-200/50 dark:hover:bg-slate-600/50 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:text-red-500 dark:hover:text-red-400'
                            }`}
                            aria-label="Thumbs down"
                          >
                            <ThumbsDown className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </div>
                    <span className="text-xs text-gray-500 dark:text-slate-400 px-1">
                      {formatDate(message.timestamp)}
                    </span>
                  </div>
                </div>
              ))
            )}
            {isLoading && (
              <div className="flex justify-start">
                <div className="flex gap-4">
                  <Avatar className="h-10 w-10 border-2 border-gray-200 dark:border-slate-700">
                    <AvatarFallback className="bg-gray-100 dark:bg-[#334155] text-gray-700 dark:text-gray-300 font-semibold">
                      AI
                    </AvatarFallback>
                  </Avatar>
                  <div className="p-4 bg-gray-100 dark:bg-[#334155] rounded-2xl">
                    <div className="flex space-x-2">
                      <div className="w-2.5 h-2.5 bg-indigo-600 dark:bg-indigo-400 rounded-full animate-bounce" />
                      <div
                        className="w-2.5 h-2.5 bg-indigo-600 dark:bg-indigo-400 rounded-full animate-bounce"
                        style={{ animationDelay: '0.1s' }}
                      />
                      <div
                        className="w-2.5 h-2.5 bg-indigo-600 dark:bg-indigo-400 rounded-full animate-bounce"
                        style={{ animationDelay: '0.2s' }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input Area */}
        <div className="bg-white/80 dark:bg-slate-800/80 backdrop-blur-md border-t border-slate-200 dark:border-slate-700 p-4 shadow-lg shadow-slate-200/50 dark:shadow-none">
          <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto">
            <div className="flex gap-4 items-end">
              <Textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Ask a question about your documents..."
                className="flex-1 min-h-[80px] max-h-[200px] resize-none bg-white dark:bg-[#334155] border border-gray-300 dark:border-slate-700 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-slate-500 rounded-2xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all duration-200 text-base"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSendMessage(e)
                  }
                }}
                disabled={isLoading || isStreaming}
              />
              <div className="relative" ref={templatesRef}>
                <button
                  type="button"
                  onClick={() => setShowTemplates(!showTemplates)}
                  className={`p-2 rounded-xl transition-all duration-200 ${
                    showTemplates
                      ? 'bg-indigo-100 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                  }`}
                  title="Prompt templates"
                >
                  <Lightbulb className="h-5 w-5" />
                </button>
                {showTemplates && (
                  <div className="absolute bottom-full mb-2 right-0 w-72 max-h-80 overflow-y-auto bg-white dark:bg-slate-800 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-700 z-50">
                    <div className="p-3 border-b border-slate-200 dark:border-slate-700">
                      <h3 className="font-semibold text-slate-800 dark:text-slate-100 text-sm">Prompt Templates</h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Click to use a template</p>
                    </div>
                    <div className="p-2">
                      {promptTemplates.map((template, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => {
                            setInputValue(template.prompt + ' ')
                            setShowTemplates(false)
                            document.querySelector('textarea')?.focus()
                          }}
                          className="w-full flex items-start gap-3 p-2.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-left"
                        >
                          <span className="text-lg">{template.icon}</span>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-slate-700 dark:text-slate-200">{template.title}</div>
                            <div className="text-xs text-slate-500 dark:text-slate-400 truncate">{template.prompt}</div>
                          </div>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-600 text-slate-500 dark:text-slate-400">
                            {template.category}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              {isSupported && (
                <button
                  type="button"
                  onClick={isListening ? stopListening : startListening}
                  className={`p-2 rounded-xl transition-all duration-200 ${
                    isListening
                      ? 'bg-red-500 text-white animate-pulse'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                  }`}
                  title={isListening ? 'Stop listening' : 'Voice input'}
                >
                  {isListening ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
                </button>
              )}
              <ModeSelector
                mode={ragMode}
                onChange={setRagMode}
                disabled={isLoading || isStreaming}
              />
              <button
                type="button"
                onClick={() => setCompareMode(!compareMode)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  compareMode
                    ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400'
                }`}
                title="Compare Normal RAG vs Agentic RAG"
              >
                {compareMode ? '⚔️ Compare ON' : '⚔️ Compare'}
              </button>
              <button
                type="button"
                onClick={() => setUseStreaming(!useStreaming)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  useStreaming
                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                }`}
                title={
                  useStreaming
                    ? 'Streaming enabled - responses appear word by word'
                    : 'Streaming disabled - full response at once'
                }
              >
                {useStreaming ? '⚡ Stream' : '📦 Batch'}
              </button>
              <Button
                type="submit"
                disabled={!inputValue.trim() || isLoading || isStreaming || isComparing}
                className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-6 h-auto rounded-2xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40"
              >
                <Send className="h-5 w-5" />
              </Button>
            </div>
          </form>
        </div>
      </main>

      {/* Keyboard Shortcuts Modal */}
      {showShortcuts && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowShortcuts(false)}
        >
          <div
            className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Keyboard className="h-5 w-5 text-indigo-500" />
                Keyboard Shortcuts
              </h2>
              <button
                onClick={() => setShowShortcuts(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-3">
              {[
                { keys: ['Ctrl', 'Enter'], action: 'Send message' },
                { keys: ['Ctrl', 'K'], action: 'Focus input' },
                { keys: ['Ctrl', 'L'], action: 'Clear chat' },
                { keys: ['Ctrl', 'E'], action: 'Export to PDF' },
                { keys: ['Ctrl', 'M'], action: 'Toggle RAG mode' },
                { keys: ['Ctrl', 'D'], action: 'Toggle dark mode' },
                { keys: ['Ctrl', '/'], action: 'Show shortcuts' },
                { keys: ['Esc'], action: 'Close modal' }
              ].map((shortcut, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between py-2 border-b border-slate-100 dark:border-slate-700 last:border-0"
                >
                  <span className="text-sm text-slate-600 dark:text-slate-400">{shortcut.action}</span>
                  <div className="flex items-center gap-1">
                    {shortcut.keys.map((key, j) => (
                      <kbd
                        key={j}
                        className="px-2 py-1 text-xs font-mono bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded border border-slate-200 dark:border-slate-600"
                      >
                        {key}
                      </kbd>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs text-slate-500 dark:text-slate-400 text-center">
              Use Cmd instead of Ctrl on Mac
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
