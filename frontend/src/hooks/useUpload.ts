'use client'

import { useState, useCallback } from 'react'
import { UploadResponse } from '@/types'
import { apiClient } from '@/lib/api'

interface UseUploadReturn {
  isUploading: boolean
  progress: number
  error: string | null
  uploadFile: (file: File) => Promise<UploadResponse | null>
  reset: () => void
}

/**
 * Custom hook for managing file uploads
 */
export function useUpload(): UseUploadReturn {
  const [isUploading, setIsUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const uploadFile = useCallback(async (file: File): Promise<UploadResponse | null> => {
    setIsUploading(true)
    setProgress(0)
    setError(null)

    try {
      // Validate file type
      const fileExt = file.name.split('.').pop()?.toLowerCase()
      if (fileExt !== 'pdf' && fileExt !== 'docx') {
        throw new Error('Only PDF and DOCX files are supported')
      }

      // Validate file size (max 10MB)
      const maxSize = 10 * 1024 * 1024 // 10MB
      if (file.size > maxSize) {
        throw new Error('File size must be less than 10MB')
      }

      // Simulate progress (actual implementation would use XMLHttpRequest for progress tracking)
      const progressInterval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval)
            return prev
          }
          return prev + 10
        })
      }, 200)

      const response = await apiClient.uploadDocument(file)
      
      clearInterval(progressInterval)
      setProgress(100)
      
      return response
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed'
      setError(errorMessage)
      return null
    } finally {
      setIsUploading(false)
      // Reset progress after a delay
      setTimeout(() => setProgress(0), 2000)
    }
  }, [])

  const reset = useCallback(() => {
    setIsUploading(false)
    setProgress(0)
    setError(null)
  }, [])

  return {
    isUploading,
    progress,
    error,
    uploadFile,
    reset,
  }
}
