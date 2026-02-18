'use client'

import { Message } from '@/types'
import { Card } from '@/components/ui/card'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { SourceCard } from './SourceCard'
import { formatDate } from '@/lib/utils'

interface MessageBubbleProps {
  message: Message
}

/**
 * Message bubble component for displaying chat messages
 */
export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <Avatar className="h-8 w-8">
        <AvatarFallback className={isUser ? 'bg-blue-600 text-white' : 'bg-slate-200'}>
          {isUser ? 'U' : 'AI'}
        </AvatarFallback>
      </Avatar>

      <div className={`flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'} flex-1`}>
        <Card className={`p-4 max-w-[80%] ${isUser ? 'bg-blue-600 text-white' : 'bg-slate-50'}`}>
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
          {message.sources && message.sources.length > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-200">
              <p className="text-xs font-semibold mb-2">Sources:</p>
              <div className="space-y-2">
                {message.sources.map((source) => (
                  <SourceCard key={source.id} source={source} />
                ))}
              </div>
            </div>
          )}
        </Card>
        <span className="text-xs text-slate-500">
          {formatDate(message.timestamp)}
        </span>
      </div>
    </div>
  )
}
