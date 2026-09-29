import React from 'react'
import { BarChart3, Plus } from 'lucide-react'

function NoCompetetiorFallback({ onCreateCompetitor }) {
  return (
    <div className="flex items-center justify-center min-h-[600px] px-4">
      <div className="w-full max-w-md">
        {/* Card Container */}
        <div 
          className="rounded-lg p-12 text-center shadow-md border"
          style={{
            backgroundColor: 'var(--card)',
            borderColor: 'var(--border)',
          }}
        >
          {/* Icon */}
          <div 
            className="flex justify-center mb-6"
            style={{ color: 'var(--secondary)' }}
          >
            <BarChart3 size={56} strokeWidth={1.5} />
          </div>

          {/* Title */}
          <h2 
            className="text-2xl font-semibold mb-3"
            style={{ color: 'var(--text)' }}
          >
            No Competitors Yet
          </h2>

          {/* Description */}
          <p 
            className="mb-8 text-base leading-relaxed"
            style={{ color: 'var(--text-light)' }}
          >
            Start tracking your competitors to monitor their pages, changes, and stay ahead of the competition.
          </p>

          {/* CTA Button */}
          {onCreateCompetitor && (
            <button
              onClick={onCreateCompetitor}
              className="w-full py-3 px-6 rounded-md font-medium flex items-center justify-center gap-2 transition-all duration-200 hover:shadow-md active:scale-95"
              style={{
                backgroundColor: 'var(--accent)',
                color: '#ffffff',
              }}
            >
              <Plus size={20} />
              Add Your First Competitor
            </button>
          )}

          {/* Alternative Info */}
          <p 
            className="text-sm mt-6"
            style={{ color: 'var(--text-light)' }}
          >
            Create a competitor profile to begin tracking
          </p>
        </div>
      </div>
    </div>
  )
}

export default NoCompetetiorFallback
