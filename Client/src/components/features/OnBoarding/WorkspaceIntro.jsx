import React from 'react';
import { Store, Target, Layers, GitCompareArrows, Sparkles } from 'lucide-react';

/* ────────────────────────────────────────────────────────────────
   IntelShift — Onboarding step 1 (capture-first).
   The page shell (OnBoarding.jsx) already renders the "Welcome to
   IntelShift" title, so this step previews what's ahead: you give us
   the URLs, we capture every site automatically, then you choose what
   to track inside your workspace — no page-picking during setup.
──────────────────────────────────────────────────────────────── */

const STEPS = [
  {
    icon: Store,
    title: 'Tell us about your store',
    body: 'Your name and website — so IntelShift knows who “you” are.',
    tint: 'var(--secondary)',
  },
  {
    icon: Target,
    title: 'Add your competitors',
    body: 'Just their URLs. The closer the competitor, the sharper the intelligence — choose deliberately.',
    tint: 'var(--primary)',
  },
  {
    icon: Layers,
    title: 'We map every store',
    body: 'IntelShift reads each homepage, menu and full catalog automatically — no setup work from you.',
    tint: 'var(--accent)',
  },
  {
    icon: GitCompareArrows,
    title: 'Choose what to track',
    body: 'Inside your workspace, pick the pages to monitor — with matches suggested for you. Analysis runs on those.',
    tint: 'var(--secondary)',
  },
];

function WorkspaceIntro() {
  return (
    <div style={{ fontFamily: 'var(--font-sans)' }}>
      <h2
        style={{
          fontSize: 20,
          fontWeight: 600,
          letterSpacing: '-0.025em',
          margin: '0 0 14px',
          color: 'var(--primary)',
        }}
      >
        How setup works
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {STEPS.map((step, i) => {
          const Icon = step.icon;
          return (
            <div
              key={step.title}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 14,
                padding: '1rem 1.125rem',
                background: 'var(--card)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <div
                style={{
                  width: 38,
                  height: 38,
                  flexShrink: 0,
                  borderRadius: 'var(--radius-sm)',
                  background: `color-mix(in srgb, ${step.tint} 12%, transparent)`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Icon size={18} style={{ color: step.tint }} />
              </div>

              <div style={{ minWidth: 0 }}>
                <p
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: 'var(--text)',
                    margin: 0,
                  }}
                >
                  <span style={{ color: 'var(--text-light)' }}>{i + 1}. </span>
                  {step.title}
                </p>
                <p
                  style={{
                    fontSize: 13,
                    lineHeight: 1.6,
                    color: 'var(--text-light)',
                    margin: '2px 0 0',
                  }}
                >
                  {step.body}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Payoff — what all this leads to, so the steps feel worth it. */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginTop: 14,
          padding: '0.85rem 1.125rem',
          background: 'var(--glow-teal)',
          border: '1px solid color-mix(in srgb, var(--secondary) 30%, transparent)',
          borderRadius: 'var(--radius)',
        }}
      >
        <Sparkles
          size={17}
          style={{ color: 'var(--secondary-dark)', flexShrink: 0 }}
        />
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: 'var(--text)' }}>
          Then IntelShift starts monitoring and delivers your{' '}
          <strong>first competitor report</strong> — no more manual checking.
        </p>
      </div>
    </div>
  );
}

export default WorkspaceIntro;
