'use client'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { MessageSquare, Upload } from 'lucide-react'

/**
 * Header component for the application
 */
export function Header() {
  return (
    <header className="border-b bg-white sticky top-0 z-10">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">
              Enterprise RAG Platform
            </h1>
            <Badge variant="secondary" className="bg-blue-100 text-blue-700">
              Beta
            </Badge>
          </div>
          <nav className="flex items-center gap-2">
            <Button variant="ghost" size="sm">
              <Upload className="h-4 w-4 mr-2" />
              Upload
            </Button>
            <Button variant="ghost" size="sm">
              <MessageSquare className="h-4 w-4 mr-2" />
              Chat
            </Button>
          </nav>
        </div>
      </div>
    </header>
  )
}
