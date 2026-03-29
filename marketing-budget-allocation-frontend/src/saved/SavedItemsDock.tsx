import { useEffect, useRef, useState } from 'react'
import type { SavedItem } from './SavedItemsStore'

type SavedItemsDockProps<TPayload> = {
  items: SavedItem<TPayload>[]
  onSaveCurrent: () => void
  onDownload: () => void
  onApply: (item: SavedItem<TPayload>) => void
  onDelete: (id: string) => void
  onRename?: (item: SavedItem<TPayload>) => void
}

export function SavedItemsDock<TPayload>({
  items,
  onSaveCurrent,
  onDownload,
  onApply,
  onDelete,
  onRename,
}: SavedItemsDockProps<TPayload>) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) return
    const onMouseDown = (event: MouseEvent) => {
      const target = event.target as Node | null
      if (!target) return
      if (rootRef.current && !rootRef.current.contains(target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [open])

  useEffect(() => {
    if (items.length === 0) {
      setOpen(false)
    }
  }, [items.length])

  return (
    <div ref={rootRef} className="fixed right-5 top-[76px] z-40">
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onDownload}
          className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
        >
          Download
        </button>
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-primary shadow-sm hover:bg-blue-100"
        >
          Saved {items.length}
        </button>
      </div>

      {open ? (
        <div className="mt-2 w-[360px] rounded-xl border border-slate-200 bg-white p-3 shadow-xl">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Saved Scenarios</p>
            <button
              type="button"
              onClick={onSaveCurrent}
              className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
            >
              Save Current
            </button>
          </div>

          <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
            {items.length === 0 ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                No saved scenarios yet.
              </div>
            ) : (
              items.map((item) => (
                <div key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-dark-text">{item.name}</p>
                      <p className="text-[11px] text-slate-500">{item.savedAtLabel}</p>
                    </div>
                    <p className="text-[11px] font-semibold text-slate-600">{item.summary.selected_brand || '-'}</p>
                  </div>
                  <p className="mt-1 text-[11px] text-slate-600">
                    Markets: {item.summary.markets_count} | Scenarios: {item.summary.scenario_count}
                  </p>
                  <p className="text-[11px] text-slate-600">
                    Revenue: {item.summary.revenue_uplift_pct == null ? '-' : `${item.summary.revenue_uplift_pct >= 0 ? '+' : ''}${item.summary.revenue_uplift_pct.toFixed(2)}%`}
                  </p>

                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() => onApply(item)}
                      className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-100"
                    >
                      Apply
                    </button>
                    {onRename ? (
                      <button
                        type="button"
                        onClick={() => onRename(item)}
                        className="rounded border border-slate-300 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-100"
                      >
                        Rename
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => onDelete(item.id)}
                      className="rounded border border-red-200 bg-red-50 px-2 py-1 text-[11px] font-semibold text-red-700 hover:bg-red-100"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}

