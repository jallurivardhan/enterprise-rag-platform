import { ChatRequest, ChatResponse, UploadResponse, Document } from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * API client for backend communication
 */
class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    
    // Add auth token if available
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    const response = await fetch(url, {
      ...options,
      headers,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      // Create error object with status for rate limit handling
      const errorObj: any = new Error(error.detail || `HTTP error! status: ${response.status}`)
      errorObj.status = response.status
      errorObj.detail = error.detail
      errorObj.response = { status: response.status, data: error }
      throw errorObj
    }

    return response.json()
  }

  /**
   * Health check endpoint
   */
  async healthCheck(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/api/health')
  }

  /**
   * Send a chat query
   */
  async chat(request: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  /**
   * Upload a document
   */
  async uploadDocument(file: File, permission: string = 'public'): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('permission', permission)

    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
    const headers: HeadersInit = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`${this.baseUrl}/api/ingest/upload`, {
      method: 'POST',
      headers,
      body: formData,
    })

    if (!response.ok) {
      if (response.status === 401) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('auth_token')
          localStorage.removeItem('user')
          window.location.href = '/login'
        }
      }
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || `HTTP error! status: ${response.status}`)
    }

    return response.json()
  }

  /**
   * Get list of documents
   */
  async getDocuments(): Promise<{ documents: Document[]; total: number }> {
    return this.request<{ documents: Document[]; total: number }>('/api/ingest/documents')
  }

  /**
   * Delete a document
   */
  async deleteDocument(documentId: string): Promise<{ success: boolean; chunks_deleted: number }> {
    return this.request<{ success: boolean; chunks_deleted: number }>(`/api/ingest/documents/${documentId}`, {
      method: 'DELETE',
    })
  }

  /**
   * Get ingestion status
   */
  async getIngestStatus(documentId: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/ingest/status/${documentId}`)
  }

  /**
   * Create an EventSource for streaming chat responses
   */
  createChatStream(query: string, conversationId?: string): EventSource {
    const params = new URLSearchParams({ query })
    if (conversationId) {
      params.append('conversation_id', conversationId)
    }
    return new EventSource(`${this.baseUrl}/api/chat/stream?${params.toString()}`)
  }

  /**
   * Get rate limit status
   */
  async getRateLimitStatus(): Promise<{ limit: number; remaining: number; reset_in_seconds: number }> {
    return this.request<{ limit: number; remaining: number; reset_in_seconds: number }>('/api/chat/rate-limit')
  }
}

export const apiClient = new ApiClient()
