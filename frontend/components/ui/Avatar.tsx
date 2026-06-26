import Image from "next/image";
import { getInitials } from "@/lib/utils";

interface AvatarProps {
  name: string;
  url: string | null;
  size?: number;
  ringColor?: string;
}

export function Avatar({ name, url, size = 48, ringColor }: AvatarProps) {
  const initials = getInitials(name);

  return (
    <div
      className="relative flex-shrink-0 rounded-full overflow-hidden"
      style={{
        width: size,
        height: size,
        outline: `2px solid ${ringColor ?? "rgba(255,255,255,0.08)"}`,
        outlineOffset: 2,
      }}
    >
      {url ? (
        <Image
          src={url}
          alt={name}
          fill
          className="object-cover object-top"
          sizes={`${size}px`}
        />
      ) : (
        <div
          className="w-full h-full flex items-center justify-center bg-card-alt text-mid font-semibold"
          style={{ fontSize: Math.max(10, Math.floor(size * 0.32)) }}
        >
          {initials}
        </div>
      )}
    </div>
  );
}
