interface SwitchProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
}

export function Switch({ checked, onChange, label }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={(e) => {
        e.stopPropagation();
        onChange(!checked);
      }}
      className={`relative h-[22px] w-[38px] flex-none cursor-pointer rounded-full border-0 p-0 transition-colors after:absolute after:top-[3px] after:left-[3px] after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-transform after:content-[''] ${
        checked ? 'bg-accent after:translate-x-4' : 'bg-line'
      }`}
    />
  );
}
