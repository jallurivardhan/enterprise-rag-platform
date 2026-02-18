'use client'

import { useEffect, useState } from 'react'

interface StreamingTextProps {
  text: string
  isStreaming?: boolean
}

/**
 * Component for displaying streaming text with typing animation
 */
export function StreamingText({ text, isStreaming = false }: StreamingTextProps) {
  const [displayedText, setDisplayedText] = useState('')

  useEffect(() => {
    if (!isStreaming) {
      setDisplayedText(text)
      return
    }

    let currentIndex = 0
    const interval = setInterval(() => {
      if (currentIndex < text.length) {
        setDisplayedText(text.slice(0, currentIndex + 1))
        currentIndex++
      } else {
        clearInterval(interval)
      }
    }, 20) // Adjust speed as needed

    return () => clearInterval(interval)
  }, [text, isStreaming])

  return (
    <span>
      {displayedText}
      {isStreaming && displayedText.length < text.length && (
        <span className="animate-pulse">|</span>
      )}
    </span>
  )
}
