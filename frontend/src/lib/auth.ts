/** Authentication utilities */

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('auth_token')
}

export function getUser(): any | null {
  if (typeof window === 'undefined') return null
  const user = localStorage.getItem('user')
  return user ? JSON.parse(user) : null
}

export function isAuthenticated(): boolean {
  return !!getToken()
}

export function logout(): void {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('user')
  localStorage.removeItem('chat_messages')
  localStorage.removeItem('conversation_id')
  window.location.href = '/login'
}

export function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken()
  
  const headers = {
    ...options.headers,
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  }
  
  return fetch(url, { ...options, headers })
}
