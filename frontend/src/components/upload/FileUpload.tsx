'use client'

import { useCallback, useState } from 'react'
import { useUpload } from '@/hooks/useUpload'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Upload, File, X } from 'lucide-react'
import { UploadProgress } from './UploadProgress'
import { formatFileSize } from '@/lib/utils'
import { toast } from '@/hooks/use-toast'

/**
 * File upload component with drag-and-drop support
 */
export function FileUpload() {
  const { isUploading, progress, error, uploadFile, reset } = useUpload()
  const [isDragging, setIsDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const handleFileSelect = useCallback(async (file: File) => {
    setSelectedFile(file)
    const result = await uploadFile(file)
    
    if (result?.success) {
      toast({
        title: 'Upload successful',
        description: `Document "${result.filename || file.name}" has been processed.`,
      })
      setSelectedFile(null)
    } else if (error) {
      toast({
        title: 'Upload failed',
        description: error,
        variant: 'destructive',
      })
    }
  }, [uploadFile, error])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const file = e.dataTransfer.files[0]
    if (file) {
      handleFileSelect(file)
    }
  }, [handleFileSelect])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setIsDragging(false)
  }, [])

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      handleFileSelect(file)
    }
  }, [handleFileSelect])

  const handleRemove = useCallback(() => {
    setSelectedFile(null)
    reset()
  }, [reset])

  return (
    <Card className="p-6">
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Upload className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">Upload Document</h3>
        </div>

        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
            isDragging
              ? 'border-blue-600 bg-blue-50'
              : 'border-slate-300 hover:border-slate-400'
          }`}
        >
          {selectedFile ? (
            <div className="space-y-2">
              <div className="flex items-center justify-center gap-2">
                <File className="h-8 w-8 text-slate-400" />
                <div className="text-left">
                  <p className="font-medium">{selectedFile.name}</p>
                  <p className="text-sm text-slate-500">
                    {formatFileSize(selectedFile.size)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRemove}
                  className="ml-2"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              {isUploading && <UploadProgress progress={progress} />}
            </div>
          ) : (
            <div className="space-y-4">
              <Upload className="h-12 w-12 mx-auto text-slate-400" />
              <div>
                <p className="text-slate-600 mb-2">
                  Drag and drop a PDF or DOCX file here, or click to browse
                </p>
                <p className="text-sm text-slate-500">
                  Maximum file size: 10MB
                </p>
              </div>
              <Button
                onClick={() => document.getElementById('file-input')?.click()}
                className="bg-blue-600 hover:bg-blue-700"
                disabled={isUploading}
              >
                Select File
              </Button>
              <input
                id="file-input"
                type="file"
                accept=".pdf,.docx"
                onChange={handleFileInput}
                className="hidden"
                disabled={isUploading}
              />
            </div>
          )}
        </div>

        {error && !isUploading && (
          <p className="text-sm text-red-600">{error}</p>
        )}
      </div>
    </Card>
  )
}
