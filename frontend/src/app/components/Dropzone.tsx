'use client'

import { useRef, useState } from 'react'

const MAX_BYTES = 100 * 1024 * 1024 // 100MB, per spec/roadmap.md

import type { Profile } from '../lib/api'

export type UploadedFile = {
  datasetId: string
  filename: string
  sizeBytes: number
  fileType?: string
  profile?: Profile | null
}

function isSupported(file: File): boolean {
  const name = file.name.toLowerCase()
  return (
    name.endsWith('.csv') ||
    name.endsWith('.xlsx') ||
    name.endsWith('.xls') ||
    file.type === 'text/csv'
  )
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

  async function acceptMany(list: FileList | File[] | null | undefined) {
    const arr = list ? Array.from(list) : []
    if (arr.length === 0) return
    setError(null)
    for (const file of arr) {
      if (!isSupported(file)) {
        setError(`${file.name}: only CSV and Excel (.xlsx/.xls) files are supported.`)
        continue
      }
      if (file.size > MAX_BYTES) {
        setError(`${file.name} is larger than 100MB. Please upload a smaller file.`)
        continue
      }
      setUploading(true)
      try {
        await onFile(file)
      } catch (e) {
        setError(e instanceof Error ? e.message : `Upload of ${file.name} failed. Please try again.`)
      } finally {
        setUploading(false)
      }
    }
  }

  const busy = disabled || uploading

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload a CSV or Excel file — drag and drop or press Enter to browse"
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
          if (!busy) void acceptMany(e.dataTransfer.files)
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
          accept=".csv,text/csv,.xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
          multiple
          className="hidden"
          data-testid="file-input"
          disabled={busy}
          onChange={(e) => {
            void acceptMany(e.target.files)
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
          {uploading ? 'Uploading…' : 'Drop CSV or Excel files here, or click to browse'}
        </p>
        <p className="mt-1 text-xs text-gray-400">
          CSV, XLSX, XLS · multiple files · up to 100MB each
        </p>
      </div>

      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      )}

      {files.length > 0 && (
        <ul
          className="mt-3 flex flex-wrap gap-2"
          aria-label="Uploaded files"
          data-testid="uploaded-files"
        >
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
