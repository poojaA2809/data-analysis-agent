'use client'

import type { UploadedFile } from './Dropzone'

// Lets the user choose which loaded datasets are in scope for the next
// question. Selected dataset_ids are sent with POST /sessions/{id}/messages.

export function DatasetPicker({
  files,
  selected,
  onToggle,
}: {
  files: UploadedFile[]
  selected: Set<string>
  onToggle: (datasetId: string) => void
}) {
  if (files.length === 0) return null

  return (
    <div
      data-testid="dataset-picker"
      className="rounded-lg border border-gray-200 bg-white p-3"
    >
      <p className="mb-2 text-xs font-medium text-gray-600">
        Datasets in scope for your next question
      </p>
      <div className="flex flex-wrap gap-2">
        {files.map((f) => {
          const on = selected.has(f.datasetId)
          return (
            <label
              key={f.datasetId}
              className={[
                'inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1 text-xs',
                on
                  ? 'border-blue-300 bg-blue-50 text-blue-800'
                  : 'border-gray-300 bg-gray-50 text-gray-500',
              ].join(' ')}
            >
              <input
                type="checkbox"
                className="h-3.5 w-3.5"
                checked={on}
                onChange={() => onToggle(f.datasetId)}
                data-testid={`dataset-toggle-${f.datasetId}`}
              />
              <span className="font-medium">{f.filename}</span>
              {f.fileType && (
                <span className="uppercase text-gray-400">{f.fileType}</span>
              )}
            </label>
          )
        })}
      </div>
    </div>
  )
}
