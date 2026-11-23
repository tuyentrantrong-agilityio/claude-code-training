import { TONE_CLASSES, initials, tone } from '../lib/format';

export type AvatarSize = 'md' | 'lg' | 'xl';

const sizes: Record<AvatarSize, string> = {
  md: 'h-[30px] w-[30px] text-[0.72rem]',
  lg: 'h-11 w-11 text-[0.95rem]',
  xl: 'h-[72px] w-[72px] text-[1.3rem]',
};

interface AvatarProps {
  name: string;
  size?: AvatarSize;
  square?: boolean;
  className?: string;
}

export function Avatar({ name, size = 'md', square = false, className = '' }: AvatarProps) {
  return (
    <span
      aria-hidden="true"
      data-testid="avatar"
      className={`inline-grid flex-none place-items-center font-bold ${sizes[size]} ${
        square ? 'rounded-[9px]' : 'rounded-full'
      } ${TONE_CLASSES[tone(name)]} ${className}`}
    >
      {initials(name)}
    </span>
  );
}
