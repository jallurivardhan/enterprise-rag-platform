"use client"

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { 
  BarChart3, 
  MessageSquare, 
  Clock, 
  ThumbsUp, 
  ThumbsDown,
  TrendingUp,
  ArrowLeft,
  FileText
} from 'lucide-react'
import { toast } from '@/hooks/use-toast'

interface Analytics {
  usage: {
    total_queries: number
    avg_response_time_ms: number
    queries_today: number
    queries_this_week: number
    avg_sources_per_query: number
  }
  feedback: {
    total: number
    positive: number
    negative: number
    satisfaction_rate: number
  }
  popular_topics: Array<{ word: string; count: number }>
  recent_queries: Array<{ query: string; timestamp: string; response_time_ms: number }>
  hourly_distribution: Array<{ hour: number; count: number }>
}

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [loading, setLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [darkMode, setDarkMode] = useState(true)

  const fetchAnalytics = async () => {
    try {
      setIsRefreshing(true)
      const token = localStorage.getItem('auth_token')
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'https://enterprise-rag-platform.onrender.com'
      const response = await fetch(`${baseUrl}/api/chat/analytics`, {
        headers: {
          ...(token && { Authorization: `Bearer ${token}` })
        }
      })
      if (response.ok) {
        const data = await response.json()
        setAnalytics(data)
        // Only show toast on manual refresh, not initial load
        if (!loading) {
          toast({
            title: '✅ Analytics Refreshed',
            description: `Updated at ${new Date().toLocaleTimeString()}`
          })
        }
      }
    } catch (error) {
      console.error('Failed to fetch analytics:', error)
      toast({
        title: '❌ Refresh Failed',
        description: 'Could not fetch analytics data',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
      setIsRefreshing(false)
    }
  }

  useEffect(() => {
    const saved = localStorage.getItem('theme')
    setDarkMode(saved !== 'light')
    fetchAnalytics()

    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      fetchAnalytics()
    }, 30000)

    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className={`min-h-screen flex items-center justify-center ${darkMode ? 'bg-[#0f172a]' : 'bg-gray-50'}`}>
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500"></div>
      </div>
    )
  }

  return (
    <div className={`min-h-screen ${darkMode ? 'bg-[#0f172a] text-white' : 'bg-gray-50 text-gray-900'}`}>
      {/* Header */}
      <header className={`border-b ${darkMode ? 'border-slate-700 bg-[#1e293b]' : 'border-gray-200 bg-white'} p-4`}>
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className={`p-2 rounded-lg ${darkMode ? 'hover:bg-slate-700' : 'hover:bg-gray-100'}`}>
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-xl font-bold flex items-center gap-2">
              <BarChart3 className="w-6 h-6 text-indigo-500" />
              Analytics Dashboard
            </h1>
          </div>
          <button
            onClick={() => fetchAnalytics()}
            disabled={isRefreshing}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-70 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isRefreshing ? (
              <>
                <span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                Refreshing...
              </>
            ) : (
              'Refresh'
            )}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            title="Total Queries"
            value={analytics?.usage.total_queries || 0}
            icon={<MessageSquare className="w-6 h-6" />}
            darkMode={darkMode}
          />
          <StatCard
            title="Avg Response Time"
            value={`${analytics?.usage.avg_response_time_ms || 0}ms`}
            icon={<Clock className="w-6 h-6" />}
            darkMode={darkMode}
          />
          <StatCard
            title="Satisfaction Rate"
            value={`${analytics?.feedback.satisfaction_rate || 0}%`}
            icon={<ThumbsUp className="w-6 h-6" />}
            darkMode={darkMode}
            highlight={true}
          />
          <StatCard
            title="Queries Today"
            value={analytics?.usage.queries_today || 0}
            icon={<TrendingUp className="w-6 h-6" />}
            darkMode={darkMode}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Feedback Summary */}
          <div className={`rounded-xl p-6 ${darkMode ? 'bg-[#1e293b]' : 'bg-white shadow-sm'}`}>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <ThumbsUp className="w-5 h-5 text-green-500" />
              Feedback Summary
            </h2>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className={darkMode ? 'text-slate-400' : 'text-gray-600'}>Positive</span>
                <span className="text-green-500 font-semibold">{analytics?.feedback.positive || 0}</span>
              </div>
              <div className={`w-full ${darkMode ? 'bg-slate-700' : 'bg-gray-200'} rounded-full h-2`}>
                <div 
                  className="bg-green-500 h-2 rounded-full" 
                  style={{ width: `${analytics?.feedback.satisfaction_rate || 0}%` }}
                ></div>
              </div>
              <div className="flex justify-between items-center">
                <span className={darkMode ? 'text-slate-400' : 'text-gray-600'}>Negative</span>
                <span className="text-red-500 font-semibold">{analytics?.feedback.negative || 0}</span>
              </div>
            </div>
          </div>

          {/* Popular Topics */}
          <div className={`rounded-xl p-6 ${darkMode ? 'bg-[#1e293b]' : 'bg-white shadow-sm'}`}>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-indigo-500" />
              Popular Topics
            </h2>
            <div className="space-y-2">
              {analytics?.popular_topics.slice(0, 5).map((topic, idx) => (
                <div key={idx} className="flex justify-between items-center">
                  <span className={darkMode ? 'text-slate-300' : 'text-gray-700'}>{topic.word}</span>
                  <span className={`px-2 py-1 rounded-full text-xs ${darkMode ? 'bg-indigo-500/20 text-indigo-300' : 'bg-indigo-100 text-indigo-700'}`}>
                    {topic.count}
                  </span>
                </div>
              ))}
              {(!analytics?.popular_topics || analytics.popular_topics.length === 0) && (
                <p className={darkMode ? 'text-slate-400' : 'text-gray-500'} style={{ fontSize: '0.875rem' }}>No data yet. Start asking questions!</p>
              )}
            </div>
          </div>

          {/* Recent Queries */}
          <div className={`rounded-xl p-6 lg:col-span-2 ${darkMode ? 'bg-[#1e293b]' : 'bg-white shadow-sm'}`}>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-indigo-500" />
              Recent Queries
            </h2>
            <div className="space-y-3">
              {analytics?.recent_queries.slice(0, 5).map((query, idx) => (
                <div 
                  key={idx} 
                  className={`p-3 rounded-lg ${darkMode ? 'bg-slate-800' : 'bg-gray-50'}`}
                >
                  <p className={darkMode ? 'text-slate-200' : 'text-gray-800'}>{query.query}</p>
                  <div className="flex gap-4 mt-2 text-xs" style={{ color: darkMode ? '#94a3b8' : '#6b7280' }}>
                    <span>{new Date(query.timestamp).toLocaleString()}</span>
                    <span>{query.response_time_ms}ms</span>
                  </div>
                </div>
              ))}
              {(!analytics?.recent_queries || analytics.recent_queries.length === 0) && (
                <p className={darkMode ? 'text-slate-400' : 'text-gray-500'} style={{ fontSize: '0.875rem' }}>No queries yet. Start a conversation!</p>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

function StatCard({ 
  title, 
  value, 
  icon, 
  darkMode, 
  highlight = false 
}: { 
  title: string
  value: string | number
  icon: React.ReactNode
  darkMode: boolean
  highlight?: boolean
}) {
  return (
    <div className={`rounded-xl p-6 ${
      highlight 
        ? 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white' 
        : darkMode ? 'bg-[#1e293b]' : 'bg-white shadow-sm'
    }`}>
      <div className="flex items-center justify-between mb-2">
        <span className={highlight ? 'text-white/80' : darkMode ? 'text-slate-400' : 'text-gray-600'}>{title}</span>
        <div className={highlight ? 'text-white/80' : 'text-indigo-500'}>{icon}</div>
      </div>
      <p className="text-3xl font-bold">{value}</p>
    </div>
  )
}
