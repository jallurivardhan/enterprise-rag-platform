'use client'

import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { FileText, Trash2 } from 'lucide-react'
import { Document } from '@/types'
import { formatDate } from '@/lib/utils'

interface SidebarProps {
  documents?: Document[]
  onDocumentSelect?: (documentId: string) => void
  onDocumentDelete?: (documentId: string) => void
}

/**
 * Sidebar component for displaying document list
 */
export function Sidebar({ documents = [], onDocumentSelect, onDocumentDelete }: SidebarProps) {
  return (
    <aside className="w-64 border-r bg-slate-50 h-full overflow-y-auto">
      <div className="p-4">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Documents</h2>
        {documents.length === 0 ? (
          <p className="text-sm text-slate-500">No documents uploaded yet.</p>
        ) : (
          <div className="space-y-2">
            {documents.map((doc) => (
              <Card
                key={doc.id}
                className="p-3 hover:bg-slate-100 cursor-pointer transition-colors"
                onClick={() => onDocumentSelect?.(doc.id)}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <FileText className="h-4 w-4 text-slate-400 flex-shrink-0" />
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {doc.filename}
                      </p>
                    </div>
                    <p className="text-xs text-slate-500">
                      {doc.chunks_count} chunks
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      {formatDate(doc.created_at)}
                    </p>
                  </div>
                  {onDocumentDelete && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        onDocumentDelete(doc.id)
                      }}
                      className="h-6 w-6 p-0 text-slate-400 hover:text-red-600"
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
