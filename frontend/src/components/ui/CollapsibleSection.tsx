import type { ReactNode } from 'react';
import { cn } from '@/utils/cn';

export interface CollapsibleSectionProps {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
  defaultOpen?: boolean;
  isDisabled?: boolean;
  disabledHint?: string;
}

export function CollapsibleSection({
  title,
  description,
  children,
  className,
  defaultOpen = false,
  isDisabled = false,
  disabledHint,
}: CollapsibleSectionProps) {
  const detailsProps = (() => {
    if (isDisabled) {
      return { open: false as const };
    }
    if (defaultOpen) {
      return { defaultOpen: true as const };
    }
    return {};
  })();

  return (
    <div
      className={cn(
        'overflow-hidden rounded-xl border border-border bg-surface text-foreground shadow-sm',
        className,
      )}
    >
      <details
        {...detailsProps}
        className={cn(
          'group [&_summary]:list-none',
          isDisabled && 'pointer-events-none',
        )}
      >
        <summary
          className={cn(
            'select-none p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-t-xl',
            isDisabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer',
          )}
        >
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-lg font-semibold leading-none">{title}</h3>
            <span
              className="inline-block text-muted-foreground transition-transform group-open:rotate-180"
              aria-hidden
            >
              ▼
            </span>
          </div>
          {!isDisabled && description ? (
            <p className="mt-1.5 text-sm text-muted-foreground">
              {description}
            </p>
          ) : null}
        </summary>
        <div
          className={cn('p-6 pt-0 rounded-b-xl', isDisabled && 'opacity-50')}
        >
          {children}
        </div>
      </details>
      {isDisabled && disabledHint ? (
        <div
          role="note"
          className="border-t border-amber-300/80 bg-amber-100 px-4 py-2.5 text-xs font-medium leading-snug text-amber-950"
        >
          {disabledHint}
        </div>
      ) : null}
    </div>
  );
}
