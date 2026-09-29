import React, { useEffect, useMemo, useState } from 'react';
import {
  CheckCircle2,
  Circle,
  LoaderCircle,
} from 'lucide-react';

function FreshDataSync({
  mode = 'boot',
  authHydrated = false,
  workspaceHydrated = false,
  bootstrapped = false,
  bootstrapPhase = 'hydrating',
}) {

  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {

    if (
      bootstrapPhase === 'ready' ||
      bootstrapPhase === 'billing-required'
    ) {
      return;
    }

    const interval = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(interval);

  }, [bootstrapPhase]);

  const phaseOrder = [
    'hydrating',
    'loading-user',
    'checking-billing',
    'loading-workspace',
    'billing-required',
    'ready',
  ];

  const currentPhaseIndex = phaseOrder.indexOf(bootstrapPhase);

  const steps =
    mode === 'auth'
      ? [
          {
            key: 'auth-hydration',
            label: 'Checking your secure session',
            phase: 'loading-user',
            hydrated: authHydrated,
          },
        ]
      : [
          {
            key: 'auth-hydration',
            label: 'Restoring account session',
            phase: 'loading-user',
            hydrated: authHydrated,
          },
          {
            key: 'billing-check',
            label: 'Checking billing status',
            phase: 'checking-billing',
            hydrated: authHydrated,
          },
          {
            key: 'workspace-hydration',
            label: 'Loading workspace',
            phase: 'loading-workspace',
            hydrated: workspaceHydrated,
          },
          {
            key: 'sync',
            label:
              bootstrapPhase === 'billing-required'
                ? 'Billing review required'
                : 'Opening your workspace',
            phase: 'ready',
            hydrated: bootstrapped,
          },
        ];

  const stepsWithStatus = steps.map((step) => {

    const stepPhaseIndex = phaseOrder.indexOf(step.phase);

    if (
      bootstrapPhase === 'billing-required' &&
      step.phase === 'ready'
    ) {
      return { ...step, status: 'pending' };
    }

    if (
      bootstrapPhase === 'ready' &&
      step.phase === 'ready'
    ) {
      return { ...step, status: 'done' };
    }

    if (
      step.hydrated &&
      stepPhaseIndex < currentPhaseIndex
    ) {
      return { ...step, status: 'done' };
    }

    if (step.phase === bootstrapPhase) {
      return { ...step, status: 'active' };
    }

    if (stepPhaseIndex < currentPhaseIndex) {
      return { ...step, status: 'done' };
    }

    return { ...step, status: 'pending' };
  });

  const doneCount = stepsWithStatus.filter(
    (step) => step.status === 'done'
  ).length;

  const activeCount = stepsWithStatus.some(
    (step) => step.status === 'active'
  )
    ? 1
    : 0;

  const progress = Math.round(
    ((doneCount + activeCount * 0.5) /
      stepsWithStatus.length) *
      100
  );

  const activeStep = stepsWithStatus.find(
    (step) => step.status === 'active'
  );

  const headline =
    activeStep?.label ||
    (bootstrapPhase === 'billing-required'
      ? 'Billing review required'
      : 'Opening your workspace');

  const statusText =
    mode === 'auth'
      ? 'Please wait while we validate your login session.'
      : bootstrapPhase === 'hydrating'
      ? 'Restoring saved session state.'
      : bootstrapPhase === 'loading-user'
      ? 'Loading your account information.'
      : bootstrapPhase === 'checking-billing'
      ? 'Checking your subscription status.'
      : bootstrapPhase === 'loading-workspace'
      ? 'Loading your workspace.'
      : bootstrapPhase === 'billing-required'
      ? 'Billing access is required before continuing.'
      : 'Everything is ready. Redirecting now...';

  const waitLabel = useMemo(() => {

    if (bootstrapPhase === 'ready') {
      return 'Completed';
    }

    if (bootstrapPhase === 'billing-required') {
      return 'Needs billing';
    }

    if (bootstrapPhase === 'loading-workspace') {
      return 'Loading workspace';
    }

    if (bootstrapPhase === 'checking-billing') {
      return 'Checking billing';
    }

    if (bootstrapPhase === 'loading-user') {
      return 'Loading account';
    }

    return 'Restoring';

  }, [bootstrapPhase]);

  const syncCopy =
    bootstrapPhase === 'billing-required'
      ? 'You can continue after billing is resolved.'
      : 'Keeping your data accurate and up to date.';

  const renderStepIcon = (status) => {

    if (status === 'done') {
      return (
        <CheckCircle2
          className="h-4 w-4 text-(--success)"
          aria-hidden="true"
        />
      );
    }

    if (status === 'active') {
      return (
        <LoaderCircle
          className="h-4 w-4 animate-spin text-(--accent)"
          aria-hidden="true"
        />
      );
    }

    return (
      <Circle
        className="h-4 w-4 text-(--text-light)"
        aria-hidden="true"
      />
    );
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-(--background) px-6 py-10">

      <div className="w-full max-w-md rounded-2xl border border-(--border) bg-(--card) p-7 shadow-(--shadow-md)">

        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[rgba(78,205,196,0.12)] text-(--secondary)">
          <LoaderCircle
            className="h-6 w-6 animate-spin"
            strokeWidth={2.2}
            aria-hidden="true"
          />
        </div>

        <h2 className="text-center font-(--font-heading) text-2xl text-(--primary)">
          {headline}
        </h2>

        <p className="mt-2 text-center text-sm text-(--text-light)">
          {statusText}
        </p>

        <div className="mt-4 flex items-center justify-between rounded-lg border border-(--border) bg-[rgba(248,249,250,0.8)] px-3 py-2 text-xs">

          <span className="font-semibold text-(--text)">
            {waitLabel}
          </span>

          <span className="text-(--text-light)">
            Elapsed: {elapsedSeconds}s
          </span>

        </div>

        <p
          className="mt-2 text-center text-xs text-(--text-light)"
          aria-live="polite"
        >
          {syncCopy}
        </p>

        <div
          className="mt-6 h-2 w-full overflow-hidden rounded-full bg-[rgba(232,234,237,0.9)]"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
          aria-label="Synchronization progress"
        >
          <div
            className="h-full rounded-full bg-(--accent) transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="mt-5 space-y-2">

          {stepsWithStatus.map((step) => (

            <div
              key={step.key}
              className="flex items-center justify-between rounded-lg border border-(--border) px-3 py-2"
            >

              <div className="flex items-center gap-2.5">

                {renderStepIcon(step.status)}

                <span className="text-sm text-(--text)">
                  {step.label}
                </span>

              </div>

              <span className="text-xs font-semibold uppercase tracking-wide text-(--text-light)">
                {step.status === 'done'
                  ? 'Done'
                  : step.status === 'active'
                  ? 'In progress'
                  : 'Pending'}
              </span>

            </div>
          ))}

        </div>

      </div>

    </div>
  );
}

export default FreshDataSync;