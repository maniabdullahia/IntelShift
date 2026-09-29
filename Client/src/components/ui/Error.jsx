import React from 'react'
import { Link, useRouteError } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'

function Error() {
  const error = useRouteError()
  const status = error?.status ? error.status : null
  const message =
    error?.statusText ||
    error?.message ||
    'An unexpected error occurred. Try refreshing the page or return home.'

  return (
    <div className="flex min-h-screen items-center justify-center bg-(--background) px-4 py-10">
      <div className="w-full max-w-xl rounded-[2rem] border border-(--border) bg-(--card) p-8 shadow-(--shadow-md)">
        <div className="flex items-center justify-center rounded-full bg-[rgba(255,107,107,0.12)] p-4 text-(--accent) shadow-sm shadow-[rgba(255,107,107,0.12)]">
          <AlertTriangle className="h-8 w-8" />
        </div>

        <div className="mt-6 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-(--accent)">Error</p>
          <h1 className="mt-4 text-3xl font-semibold text-(--primary)">Something went wrong</h1>
          <p className="mt-3 text-sm leading-6 text-(--text-light)">
            {status ? `Status ${status}: ` : ''}
            {message}
          </p>
        </div>

        <div className="mt-8 grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="inline-flex items-center justify-center rounded-xl bg-(--accent) px-4 py-3 text-sm font-semibold text-(--background) transition hover:bg-[rgba(255,107,107,0.9)]"
          >
            Reload page
          </button>

          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-xl border border-(--border) bg-[rgba(78,205,196,0.08)] px-4 py-3 text-sm font-semibold text-(--primary) transition hover:bg-[rgba(78,205,196,0.16)]"
          >
            Return to dashboard
          </Link>
        </div>
      </div>
    </div>
  )
}

export default Error
