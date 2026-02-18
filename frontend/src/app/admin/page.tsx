"use client"

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Users, FileText, BarChart3, Trash2, Shield } from 'lucide-react'

interface User {
  id: string
  username: string
  email: string
  role: string
  created_at: string
}

interface Document {
  id: string
  filename: string
  owner_id: string
  permission: string
  chunks_count: number
  created_at: string
}

export default function AdminPage() {
  const router = useRouter()
  const [users, setUsers] = useState<User[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [analytics, setAnalytics] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('users')

  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    const userStr = localStorage.getItem('user')
    const user = userStr ? JSON.parse(userStr) : {}
    
    if (!token || user.role !== 'admin') {
      router.push('/')
      return
    }
    
    fetchData()
  }, [router])

  const fetchData = async () => {
    const token = localStorage.getItem('auth_token')
    const headers = { 'Authorization': `Bearer ${token}` }
    
    try {
      const [usersRes, docsRes, analyticsRes] = await Promise.all([
        fetch('http://localhost:8000/api/admin/users', { headers }),
        fetch('http://localhost:8000/api/admin/documents', { headers }),
        fetch('http://localhost:8000/api/admin/analytics', { headers })
      ])
      
      if (usersRes.ok) {
        const data = await usersRes.json()
        setUsers(data.users || [])
      }
      if (docsRes.ok) {
        const data = await docsRes.json()
        setDocuments(data.documents || [])
      }
      if (analyticsRes.ok) {
        setAnalytics(await analyticsRes.json())
      }
    } catch (error) {
      console.error('Failed to fetch admin data:', error)
    } finally {
      setLoading(false)
    }
  }

  const deleteDocument = async (docId: string) => {
    if (!confirm('Delete this document?')) return
    
    const token = localStorage.getItem('auth_token')
    const response = await fetch(`http://localhost:8000/api/admin/documents/${docId}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    })
    
    if (response.ok) {
      setDocuments(documents.filter(d => d.id !== docId))
    }
  }

  const toggleRole = async (userId: string, currentRole: string) => {
    const newRole = currentRole === 'admin' ? 'user' : 'admin'
    const token = localStorage.getItem('auth_token')
    
    const response = await fetch(
      `http://localhost:8000/api/admin/users/${userId}/role?role=${newRole}`,
      {
        method: 'PATCH',
        headers: { 'Authorization': `Bearer ${token}` }
      }
    )
    
    if (response.ok) {
      setUsers(users.map(u => u.id === userId ? {...u, role: newRole} : u))
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#0f172a] text-white">
      <header className="border-b border-slate-700 bg-[#1e293b] p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="p-2 rounded-lg hover:bg-slate-700">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Shield className="w-6 h-6 text-purple-500" />
              Admin Dashboard
            </h1>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-[#1e293b] rounded-xl p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-slate-400">Total Users</span>
              <Users className="w-5 h-5 text-blue-500" />
            </div>
            <p className="text-3xl font-bold">{analytics?.total_users || 0}</p>
          </div>
          <div className="bg-[#1e293b] rounded-xl p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-slate-400">Total Documents</span>
              <FileText className="w-5 h-5 text-green-500" />
            </div>
            <p className="text-3xl font-bold">{analytics?.total_documents || 0}</p>
          </div>
          <div className="bg-[#1e293b] rounded-xl p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-slate-400">Total Queries</span>
              <BarChart3 className="w-5 h-5 text-purple-500" />
            </div>
            <p className="text-3xl font-bold">{analytics?.usage?.total_queries || 0}</p>
          </div>
          <div className="bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-white/80">Satisfaction</span>
            </div>
            <p className="text-3xl font-bold">{analytics?.feedback?.satisfaction_rate || 0}%</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-4 mb-6">
          <button
            onClick={() => setActiveTab('users')}
            className={`px-4 py-2 rounded-lg ${activeTab === 'users' ? 'bg-purple-600' : 'bg-slate-700'}`}
          >
            Users ({users.length})
          </button>
          <button
            onClick={() => setActiveTab('documents')}
            className={`px-4 py-2 rounded-lg ${activeTab === 'documents' ? 'bg-purple-600' : 'bg-slate-700'}`}
          >
            Documents ({documents.length})
          </button>
        </div>

        {/* Users Table */}
        {activeTab === 'users' && (
          <div className="bg-[#1e293b] rounded-xl overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-800">
                <tr>
                  <th className="text-left p-4">Username</th>
                  <th className="text-left p-4">Email</th>
                  <th className="text-left p-4">Role</th>
                  <th className="text-left p-4">Created</th>
                  <th className="text-left p-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(user => (
                  <tr key={user.id} className="border-t border-slate-700">
                    <td className="p-4">{user.username}</td>
                    <td className="p-4 text-slate-400">{user.email}</td>
                    <td className="p-4">
                      <span className={`px-2 py-1 rounded-full text-xs ${
                        user.role === 'admin' ? 'bg-purple-500/20 text-purple-400' : 'bg-blue-500/20 text-blue-400'
                      }`}>
                        {user.role}
                      </span>
                    </td>
                    <td className="p-4 text-slate-400">{new Date(user.created_at).toLocaleDateString()}</td>
                    <td className="p-4">
                      <button
                        onClick={() => toggleRole(user.id, user.role)}
                        className="text-sm text-purple-400 hover:text-purple-300"
                      >
                        Make {user.role === 'admin' ? 'User' : 'Admin'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Documents Table */}
        {activeTab === 'documents' && (
          <div className="bg-[#1e293b] rounded-xl overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-800">
                <tr>
                  <th className="text-left p-4">Filename</th>
                  <th className="text-left p-4">Owner</th>
                  <th className="text-left p-4">Permission</th>
                  <th className="text-left p-4">Chunks</th>
                  <th className="text-left p-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map(doc => (
                  <tr key={doc.id} className="border-t border-slate-700">
                    <td className="p-4">{doc.filename}</td>
                    <td className="p-4 text-slate-400">{doc.owner_id}</td>
                    <td className="p-4">
                      <span className={`px-2 py-1 rounded-full text-xs ${
                        doc.permission === 'private' ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'
                      }`}>
                        {doc.permission || 'public'}
                      </span>
                    </td>
                    <td className="p-4">{doc.chunks_count}</td>
                    <td className="p-4">
                      <button
                        onClick={() => deleteDocument(doc.id)}
                        className="text-red-400 hover:text-red-300"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
