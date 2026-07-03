'use client'

import { useRef, useState } from 'react'

const MAX_BYTES = 100 * 1024 * 1024 // 100MB, per spec/roadmap.md

export type UploadedFile = {
  datasetId: string
  filename: string
  sizeBytes: number
}

function isCsv(file: File): boolean {
  const name = file.name.toLowerCase()
  return name.endsWith('.csv') || file.type === 'text/csv'
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function Dropzone({
  onFile,
  files,
  disabled,
}: {
  onFile: (file: File) => Promise<void> | void
  files: UploadedFile[]
  disabled?: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  async function accept(file: File | undefined | null) {
    if (!file) return
    setError(null)
    if (!isCsv(file)) {
      setError('Only CSV files are supported in Phase 1. Excel arrives in Phase 2.')
      return
    }
    if (file.size > MAX_BYTES) {
      setError('That file is larger than 100MB. Please upload a smaller CSV.')
      return
    }
    setUploading(true)
    try {
      await onFile(file)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  const busy = disabled || uploading

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload a CSV file — drag and drop or press Enter to browse"
        aria-disabled={busy}
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (!busy && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          if (!busy) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (!busy) void accept(e.dataTransfer.files?.[0])
        }}
        className={[
          'flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition',
          dragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 bg-white hover:border-blue-400',
          busy ? 'cursor-not-allowed opacity-60' : '',
        ].join(' ')}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          data-testid="file-input"
          disabled={busy}
          onChange={(e) => {
            void accept(e.target.files?.[0])
            e.target.value = ''
          }}
        />
        <svg
          className="mb-2 h-8 w-8 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
          />
        </svg>
        <p className="text-sm font-medium text-gray-700">
          {uploading ? 'Uploading…' : 'Drop a CSV here, or click to browse'}
        </p>
        <p className="mt-1 text-xs text-gray-400">CSV only · up to 100MB</p>
      </div>

      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      )}

      {files.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2" aria-label="Uploaded files">
          {files.map((f) => (
            <li
              key={f.datasetId}
              className="inline-flex items-center gap-2 rounded-full border border-green-200 bg-green-50 px-3 py-1 text-xs text-green-800"
            >
              <span className="font-medium">{f.filename}</span>
              <span className="text-green-600">{formatSize(f.sizeBytes)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
