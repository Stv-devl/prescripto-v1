import { cn } from "@/lib/utils";

/**
 * Props for the NoiseBackground component.
 */
interface NoiseBackgroundProps {
  filterId: string;
  width?: number;
  height?: number;
  rounded?: string;
  seed?: number;
  className?: string;
  /** Primary gradient colour, hex */
  primaryColor?: string;
  /** Secondary gradient colour, hex */
  secondaryColor?: string;
  /** Flood colour of the noise layer, rgba */
  noiseColor?: string;
  /** Gradient direction, e.g. "90deg" for left-to-right; defaults to "135deg" */
  gradientDirection?: string;
}

/**
 * Noise background SVG pattern with layered effects.
 * Creates a textured background using 3 superposed layers:
 * 1. Base gradient background
 * 2. Gradient overlay with mix-blend-mode
 * 3. SVG fractal noise texture
 */
export function NoiseBackground({
  filterId,
  width = 608,
  height = 364,
  rounded = "20px",
  seed = 2925,
  className,
  primaryColor = "#3b82f6",
  secondaryColor = "#1e40af",
  noiseColor = "rgba(59, 130, 246, 0.7)",
  gradientDirection = "135deg",
}: NoiseBackgroundProps): React.ReactElement {
  return (
    <div
      className={cn("absolute inset-0 overflow-hidden", className)}
      style={{ borderRadius: rounded }}
    >
      {/* Layer 1: Base gradient background */}
      <div
        className="absolute inset-0"
        style={{
          background: `linear-gradient(${gradientDirection}, ${primaryColor} 0%, ${secondaryColor} 100%)`,
          borderRadius: rounded,
        }}
      />

      {/* Layer 2: Gradient overlay with mix-blend-mode */}
      <div
        className="absolute inset-0 mix-blend-overlay"
        style={{
          background: `linear-gradient(${gradientDirection}, ${primaryColor} 29.94%, ${secondaryColor} 106.24%)`,
          borderRadius: rounded,
        }}
      />

      {/* Layer 3: SVG Noise texture */}
      <svg
        className="absolute inset-0 w-full h-full"
        xmlns="http://www.w3.org/2000/svg"
        viewBox={`0 0 ${width} ${height}`}
        fill="none"
        preserveAspectRatio="none"
        style={{ borderRadius: rounded }}
      >
        <g filter={`url(#${filterId})`}>
          <rect
            y={height}
            width={height}
            height={width}
            rx={rounded === "0" ? "0" : "20"}
            transform={`rotate(-90 0 ${height})`}
            fill={primaryColor}
            fillOpacity="0.3"
          />
        </g>
        <defs>
          <filter
            id={filterId}
            x="0"
            y="0"
            width={width}
            height={height}
            filterUnits="userSpaceOnUse"
            colorInterpolationFilters="sRGB"
          >
            <feFlood floodOpacity="0" result="BackgroundImageFix" />
            <feBlend
              mode="normal"
              in="SourceGraphic"
              in2="BackgroundImageFix"
              result="shape"
            />
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.4 0.4"
              stitchTiles="stitch"
              numOctaves="3"
              result="noise"
              seed={seed}
            />
            <feColorMatrix
              in="noise"
              type="luminanceToAlpha"
              result="alphaNoise"
            />
            <feComponentTransfer in="alphaNoise" result="coloredNoise1">
              <feFuncA
                type="discrete"
                tableValues="1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
              />
            </feComponentTransfer>
            <feComposite
              operator="in"
              in2="shape"
              in="coloredNoise1"
              result="noise1Clipped"
            />
            <feFlood floodColor={noiseColor} result="color1Flood" />
            <feComposite
              operator="in"
              in2="noise1Clipped"
              in="color1Flood"
              result="color1"
            />
            <feMerge result={`effect1_noise_${filterId}`}>
              <feMergeNode in="shape" />
              <feMergeNode in="color1" />
            </feMerge>
          </filter>
        </defs>
      </svg>
    </div>
  );
}
