import { cn } from '@/utils/cn';
import { Label } from './label';

const selectClassName =
  'flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background disabled:cursor-not-allowed disabled:opacity-50';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  isDisabled?: boolean;
  description?: string;
  className?: string;
  emptyOption?: { label: string };
  placeholder?: string;
}

export function Select({
  id,
  label,
  value,
  onChange,
  options,
  isDisabled = false,
  description,
  className,
  emptyOption,
  placeholder,
}: SelectProps) {
  const showPlaceholder = placeholder && options.length === 0;

  return (
    <div className={cn('space-y-2', className)}>
      <Label htmlFor={id}>{label}</Label>
      <select
        id={id}
        className={selectClassName}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={isDisabled}
      >
        {showPlaceholder ? (
          <option value="">{placeholder}</option>
        ) : (
          <>
            {emptyOption ? <option value="">{emptyOption.label}</option> : null}
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </>
        )}
      </select>
      {description ? (
        <p className="text-xs text-muted-foreground">{description}</p>
      ) : null}
    </div>
  );
}
