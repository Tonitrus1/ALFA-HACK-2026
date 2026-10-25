import { useLayoutEffect, useRef, useState } from 'react';
import type { InputHTMLAttributes } from 'react';
import { useController } from 'react-hook-form';
import type { FieldPath, FieldValues, UseControllerProps } from 'react-hook-form';
import { formatAmount } from '../lib/money';

type MoneyInputProps<T extends FieldValues, N extends FieldPath<T>> = Pick<
  UseControllerProps<T, N>,
  'control' | 'name' | 'rules'
> &
  Omit<InputHTMLAttributes<HTMLInputElement>, 'name' | 'value' | 'defaultValue' | 'onChange'> & {
    onValueChange?: () => void;
  };

export function MoneyInput<T extends FieldValues, N extends FieldPath<T>>({
  control,
  name,
  rules,
  onValueChange,
  ...props
}: MoneyInputProps<T, N>) {
  const { field } = useController({ control, name, rules });
  const input = useRef<HTMLInputElement | null>(null);
  const [selection, setSelection] = useState<{ position: number }>();
  useLayoutEffect(() => {
    if (selection && input.current === document.activeElement)
      input.current?.setSelectionRange(selection.position, selection.position);
  }, [selection]);

  return (
    <input
      {...props}
      name={field.name}
      ref={(element) => {
        input.current = element;
        field.ref(element);
      }}
      inputMode="decimal"
      value={formatAmount(String(field.value ?? ''))}
      onBlur={(event) => {
        field.onBlur();
        props.onBlur?.(event);
      }}
      onChange={(event) => {
        const text = event.currentTarget.value;
        const beforeCaret = text.slice(0, event.currentTarget.selectionStart ?? text.length);
        const characters = beforeCaret.replace(/\s/g, '').length;
        const raw = text.replace(/\s/g, '');
        const formatted = formatAmount(raw);
        let position = 0;
        for (let seen = 0; position < formatted.length && seen < characters; position++)
          if (!/\s/.test(formatted[position])) seen++;
        setSelection({ position });
        field.onChange(raw);
        onValueChange?.();
      }}
      onKeyDown={(event) => {
        props.onKeyDown?.(event);
        if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
        const element = event.currentTarget;
        const position = element.selectionStart;
        if (position === null || position !== element.selectionEnd) return;
        // Delete the adjacent digit together with a separator so deletion never gets stuck.
        if (event.key === 'Backspace' && position > 1 && element.value[position - 1] === ' ')
          element.setSelectionRange(position - 2, position);
        if (event.key === 'Delete' && element.value[position] === ' ')
          element.setSelectionRange(position, position + 2);
      }}
    />
  );
}
