'use client'

import { Source } from '@/types'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ExternalLink } from 'lucide-react'

interface SourceCardProps {
  source: Source
}

/**
 * Source card component for displaying document sources
 */
export function SourceCard({ source }: SourceCardProps) {
  const handleClick = () => {
    // TODO: Implement source navigation/viewing
    console.log('Source clicked:', source)
  }

  return (
    <Card className="p-2 hover:bg-slate-100 transition-colors cursor-pointer">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-slate-700 truncate">
              {source.metadata.filename || source.metadata.source_file}
            </span>
            <Badge variant="secondary" className="text-xs">
              {source.score.toFixed(2)}
            </Badge>
          </div>
          {source.metadata.chunk_index !== undefined && (
            <p className="text-xs text-slate-500">
              Chunk {source.metadata.chunk_index + 1}
            </p>
          )}
          {source.content && (
            <p className="text-xs text-slate-600 mt-1 line-clamp-2">
              {source.content}
            </p>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleClick}
          className="h-6 w-6 p-0 flex-shrink-0"
        >
          <ExternalLink className="h-3 w-3" />
        </Button>
      </div>
    </Card>
  )
}
