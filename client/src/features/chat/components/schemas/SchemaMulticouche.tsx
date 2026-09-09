import { z } from "zod";
import {
  NATURE_COLORS,
  NATURE_PATTERNS,
  SCHEMA_CONFIG,
  coucheSchema,
  type Couche,
  type SchemaConfig,
} from "./multicoucheConfig";

interface SchemaMulticoucheProps {
  params: Record<string, string>;
  schemaType?: string;
}

const MIN_LAYER_H = 20;
const MAX_LAYER_H = 80;
const PAD_Y = 40;
/** Room above the layers for the title, in px. */
const TITLE_H = 20;
/** Room below the layers for the title and the total dimension, in px. */
const TITLE_AND_TOTAL_H = 60;
const LAYER_X = 90;
const LAYER_W = 300;
const LABEL_X = 405;
const LABEL_W = 175;
const COTE_X = 70;
const TOTAL_X = 18;

/** Known params that are rendered inside the SVG (not shown as extra text). */
const CONSUMED_KEYS = new Set(["couches"]);

/**
 * SVG patterns for construction material hatching.
 * Each entry renders a <pattern> inside <defs>.
 */
function renderPattern(nature: string): React.ReactElement | null {
  const id = NATURE_PATTERNS[nature];
  if (!id) return null;

  switch (nature) {
    case "beton":
    case "beton_arme":
      return (
        <pattern id={id} width="10" height="10" patternUnits="userSpaceOnUse">
          <line
            x1="0"
            y1="0"
            x2="10"
            y2="10"
            stroke="#666"
            strokeWidth="0.5"
            opacity={0.4}
          />
          <line
            x1="10"
            y1="0"
            x2="0"
            y2="10"
            stroke="#666"
            strokeWidth="0.5"
            opacity={0.4}
          />
        </pattern>
      );
    case "chape":
    case "mortier":
      return (
        <pattern id={id} width="12" height="4" patternUnits="userSpaceOnUse">
          <line
            x1="0"
            y1="2"
            x2="12"
            y2="2"
            stroke="#8B7355"
            strokeWidth="0.6"
            opacity={0.5}
          />
        </pattern>
      );
    case "isolant_thermique":
    case "isolant_acoustique":
      return (
        <pattern id={id} width="16" height="8" patternUnits="userSpaceOnUse">
          <path
            d="M0,6 Q4,0 8,6 Q12,12 16,6"
            fill="none"
            stroke="#888"
            strokeWidth="0.6"
            opacity={0.45}
          />
        </pattern>
      );
    case "etancheite":
      return (
        <pattern id={id} width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="#333" opacity={0.3} />
        </pattern>
      );
    case "pare_vapeur":
    case "film_pe":
      return (
        <pattern id={id} width="12" height="6" patternUnits="userSpaceOnUse">
          <line
            x1="0"
            y1="3"
            x2="6"
            y2="3"
            stroke="#456"
            strokeWidth="0.6"
            opacity={0.5}
          />
        </pattern>
      );
    case "revetement":
    case "carrelage":
      return (
        <pattern id={id} width="12" height="12" patternUnits="userSpaceOnUse">
          <line
            x1="0"
            y1="0"
            x2="0"
            y2="12"
            stroke="#8B7355"
            strokeWidth="0.4"
            opacity={0.35}
          />
          <line
            x1="0"
            y1="0"
            x2="12"
            y2="0"
            stroke="#8B7355"
            strokeWidth="0.4"
            opacity={0.35}
          />
        </pattern>
      );
    case "enduit":
      return (
        <pattern id={id} width="8" height="8" patternUnits="userSpaceOnUse">
          <circle cx="4" cy="4" r="0.8" fill="#999" opacity={0.4} />
        </pattern>
      );
    case "plaque_platre":
      return (
        <pattern id={id} width="14" height="6" patternUnits="userSpaceOnUse">
          <line
            x1="0"
            y1="3"
            x2="14"
            y2="3"
            stroke="#aaa"
            strokeWidth="0.4"
            opacity={0.3}
          />
        </pattern>
      );
    case "bois":
      return (
        <pattern id={id} width="20" height="8" patternUnits="userSpaceOnUse">
          <path
            d="M0,2 Q5,0 10,2 Q15,4 20,2"
            fill="none"
            stroke="#8B6914"
            strokeWidth="0.5"
            opacity={0.4}
          />
          <path
            d="M0,6 Q5,4 10,6 Q15,8 20,6"
            fill="none"
            stroke="#8B6914"
            strokeWidth="0.5"
            opacity={0.4}
          />
        </pattern>
      );
    case "metal":
      return (
        <pattern id={id} width="8" height="8" patternUnits="userSpaceOnUse">
          <line
            x1="0"
            y1="0"
            x2="8"
            y2="8"
            stroke="#556"
            strokeWidth="0.5"
            opacity={0.4}
          />
        </pattern>
      );
    case "gravier":
      return (
        <pattern id={id} width="10" height="10" patternUnits="userSpaceOnUse">
          <circle cx="3" cy="3" r="1.2" fill="#8B7355" opacity={0.35} />
          <circle cx="8" cy="7" r="1" fill="#8B7355" opacity={0.35} />
        </pattern>
      );
    case "enrobe":
      return (
        <pattern id={id} width="6" height="6" patternUnits="userSpaceOnUse">
          <line
            x1="0"
            y1="0"
            x2="6"
            y2="6"
            stroke="#222"
            strokeWidth="0.7"
            opacity={0.4}
          />
        </pattern>
      );
    case "grave":
      return (
        <pattern id={id} width="12" height="10" patternUnits="userSpaceOnUse">
          <polygon
            points="6,1 3,9 9,9"
            fill="none"
            stroke="#8B7355"
            strokeWidth="0.5"
            opacity={0.4}
          />
        </pattern>
      );
    case "hourdis":
      return (
        <pattern id={id} width="16" height="10" patternUnits="userSpaceOnUse">
          <rect
            x="0"
            y="0"
            width="16"
            height="10"
            fill="none"
            stroke="#8B7355"
            strokeWidth="0.4"
            opacity={0.35}
          />
          <line
            x1="8"
            y1="0"
            x2="8"
            y2="10"
            stroke="#8B7355"
            strokeWidth="0.4"
            opacity={0.35}
          />
        </pattern>
      );
    case "geotextile":
      return (
        <pattern id={id} width="6" height="6" patternUnits="userSpaceOnUse">
          <line
            x1="0"
            y1="0"
            x2="6"
            y2="6"
            stroke="#5a8a6a"
            strokeWidth="0.3"
            opacity={0.4}
          />
          <line
            x1="6"
            y1="0"
            x2="0"
            y2="6"
            stroke="#5a8a6a"
            strokeWidth="0.3"
            opacity={0.4}
          />
        </pattern>
      );
    case "tuile":
      return (
        <pattern id={id} width="16" height="10" patternUnits="userSpaceOnUse">
          <path
            d="M0,10 Q8,2 16,10"
            fill="none"
            stroke="#a05535"
            strokeWidth="0.6"
            opacity={0.45}
          />
        </pattern>
      );
    case "ecran_sous_toiture":
      return (
        <pattern id={id} width="6" height="6" patternUnits="userSpaceOnUse">
          <circle cx="3" cy="3" r="0.5" fill="#5a7a8a" opacity={0.35} />
        </pattern>
      );
    case "ossature_isolant":
      return (
        <pattern id={id} width="20" height="20" patternUnits="userSpaceOnUse">
          {/* Insulation wavy background */}
          <path
            d="M0,6 Q5,2 10,6 Q15,10 20,6"
            fill="none"
            stroke="#888"
            strokeWidth="0.5"
            opacity={0.35}
          />
          <path
            d="M0,14 Q5,10 10,14 Q15,18 20,14"
            fill="none"
            stroke="#888"
            strokeWidth="0.5"
            opacity={0.35}
          />
          {/* Vertical metal stud */}
          <line
            x1="10"
            y1="0"
            x2="10"
            y2="20"
            stroke="#556"
            strokeWidth="1.5"
            opacity={0.5}
          />
        </pattern>
      );
    default:
      return null;
  }
}

function parseCouches(raw: string): Couche[] | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    const result = z.array(coucheSchema).safeParse(parsed);
    return result.success ? result.data : null;
  } catch {
    return null;
  }
}

function computeLayerHeights(couches: Couche[]): number[] {
  const thicknesses = couches.map((c) => {
    const v = parseFloat(c.epaisseur);
    return Number.isFinite(v) && v > 0 ? v : 1;
  });

  const maxThick = Math.max(...thicknesses);
  if (maxThick === 0) return thicknesses.map(() => MIN_LAYER_H);

  return thicknesses.map((t) => {
    const ratio = t / maxThick;
    return Math.round(MIN_LAYER_H + ratio * (MAX_LAYER_H - MIN_LAYER_H));
  });
}

/**
 * Dynamic multilayer construction schema.
 * Renders stacked layers (vertical or horizontal) with dimension arrows,
 * material patterns, and labels.
 */
export function SchemaMulticouche({
  params,
  schemaType,
}: SchemaMulticoucheProps): React.ReactElement | null {
  if (!params.couches) return null;

  const couches = parseCouches(params.couches);
  if (!couches || couches.length === 0) return null;

  const config = schemaType ? SCHEMA_CONFIG[schemaType] : undefined;
  const orientation = config?.orientation ?? "vertical";
  const label = config?.label ?? "Composition multicouche";

  const usedNatures = new Set(couches.map((c) => c.nature));

  const extraParams = Object.entries(params).filter(
    ([key]) => !CONSUMED_KEYS.has(key),
  );

  if (orientation === "horizontal") {
    return renderHorizontal(
      couches,
      label,
      usedNatures,
      extraParams,
      schemaType,
      config,
    );
  }

  return renderVertical(couches, label, usedNatures, extraParams);
}

function renderVertical(
  couches: Couche[],
  label: string,
  usedNatures: Set<string>,
  extraParams: [string, string][],
): React.ReactElement {
  const heights = computeLayerHeights(couches);
  const totalLayerH = heights.reduce((a, b) => a + b, 0);
  const svgH = totalLayerH + PAD_Y * 2 + TITLE_AND_TOTAL_H;
  const svgW = LABEL_X + LABEL_W + 10;

  let curY = PAD_Y + TITLE_H;
  const layerYs = heights.map((h) => {
    const y = curY;
    curY += h;
    return y;
  });
  const totalTop = layerYs[0];
  const totalBot = layerYs[layerYs.length - 1] + heights[heights.length - 1];

  return (
    <figure>
      <svg
        viewBox={`0 0 ${svgW} ${svgH}`}
        className="w-full max-w-2xl"
        role="img"
        aria-label={`Coupe — ${label}`}
      >
        <defs>
          <marker
            id="mc-arr-s"
            markerWidth="7"
            markerHeight="5"
            refX="0"
            refY="2.5"
            orient="auto"
          >
            <path
              d="M7,0 L0,2.5 L7,5"
              fill="none"
              stroke="#E63946"
              strokeWidth="0.8"
            />
          </marker>
          <marker
            id="mc-arr-e"
            markerWidth="7"
            markerHeight="5"
            refX="7"
            refY="2.5"
            orient="auto"
          >
            <path
              d="M0,0 L7,2.5 L0,5"
              fill="none"
              stroke="#E63946"
              strokeWidth="0.8"
            />
          </marker>
          {[...usedNatures].map((n) => (
            <g key={n}>{renderPattern(n)}</g>
          ))}
        </defs>

        {/* Background */}
        <rect width={svgW} height={svgH} fill="hsl(220 14% 90%)" rx="6" />

        {/* Title */}
        <text
          x={svgW / 2}
          y={PAD_Y + 4}
          textAnchor="middle"
          fontSize="13"
          fill="#2C3E50"
          fontWeight="bold"
        >
          {label}
        </text>

        {/* Layers */}
        {couches.map((couche, i) => {
          const y = layerYs[i];
          const h = heights[i];
          const color = NATURE_COLORS[couche.nature] ?? "#ddd";
          const patternId = NATURE_PATTERNS[couche.nature];

          return (
            <g key={i}>
              {/* Filled rect */}
              <rect
                x={LAYER_X}
                y={y}
                width={LAYER_W}
                height={h}
                fill={color}
                stroke="#2C3E50"
                strokeWidth="1"
              />
              {/* Pattern overlay */}
              {patternId && (
                <rect
                  x={LAYER_X}
                  y={y}
                  width={LAYER_W}
                  height={h}
                  fill={`url(#${patternId})`}
                />
              )}
              {/* Right label: name + thickness (wrapping) */}
              <foreignObject
                x={LABEL_X}
                y={y + 2}
                width={LABEL_W}
                height={h - 4 > 14 ? h - 4 : 30}
              >
                <div
                  style={{
                    fontSize: "10px",
                    color: "#2C3E50",
                    lineHeight: "1.3",
                    overflow: "visible",
                  }}
                >
                  {couche.nom} — {couche.epaisseur}
                </div>
              </foreignObject>

              {/* Left dimension arrow for this layer */}
              <line
                x1={COTE_X - 10}
                y1={y}
                x2={COTE_X}
                y2={y}
                stroke="#E63946"
                strokeWidth="0.8"
              />
              <line
                x1={COTE_X - 10}
                y1={y + h}
                x2={COTE_X}
                y2={y + h}
                stroke="#E63946"
                strokeWidth="0.8"
              />
              <line
                x1={COTE_X - 5}
                y1={y}
                x2={COTE_X - 5}
                y2={y + h}
                stroke="#E63946"
                strokeWidth="0.8"
                markerStart="url(#mc-arr-s)"
                markerEnd="url(#mc-arr-e)"
              />
              <text
                x={COTE_X - 12}
                y={y + h / 2 + 3}
                textAnchor="end"
                fontSize="9"
                fill="#E63946"
                fontWeight="bold"
              >
                {couche.epaisseur}
              </text>
            </g>
          );
        })}

        {/* Total dimension arrow (far left) */}
        <line
          x1={TOTAL_X - 5}
          y1={totalTop}
          x2={TOTAL_X + 5}
          y2={totalTop}
          stroke="#E63946"
          strokeWidth="0.8"
        />
        <line
          x1={TOTAL_X - 5}
          y1={totalBot}
          x2={TOTAL_X + 5}
          y2={totalBot}
          stroke="#E63946"
          strokeWidth="0.8"
        />
        <line
          x1={TOTAL_X}
          y1={totalTop}
          x2={TOTAL_X}
          y2={totalBot}
          stroke="#E63946"
          strokeWidth="1"
          markerStart="url(#mc-arr-s)"
          markerEnd="url(#mc-arr-e)"
        />
        <text
          x={TOTAL_X - 4}
          y={(totalTop + totalBot) / 2 + 4}
          textAnchor="end"
          fontSize="10"
          fill="#E63946"
          fontWeight="bold"
          transform={`rotate(-90, ${TOTAL_X - 4}, ${(totalTop + totalBot) / 2})`}
        >
          Total
        </text>
      </svg>

      {extraParams.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-gray-600">
          {extraParams.map(([key, value]) => (
            <li key={key}>
              <span className="font-medium">{key.replace(/_/g, " ")} :</span>{" "}
              {value}
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}

function renderHorizontal(
  couches: Couche[],
  label: string,
  usedNatures: Set<string>,
  extraParams: [string, string][],
  schemaType?: string,
  config?: SchemaConfig,
): React.ReactElement {
  const thicknesses = couches.map((c) => {
    const v = parseFloat(c.epaisseur);
    return Number.isFinite(v) && v > 0 ? v : 1;
  });
  const maxThick = Math.max(...thicknesses);

  const MIN_W = 15;
  const MAX_W = 140;
  const widths = thicknesses.map((t) => {
    const ratio = t / maxThick;
    return Math.round(MIN_W + ratio * (MAX_W - MIN_W));
  });

  const LAYER_Y_H = 200;
  const LAYER_TOP = 60;
  const GAP = 2;
  const LEFT_PAD = 60;
  const totalW = widths.reduce((a, b) => a + b, 0) + GAP * (widths.length - 1);
  const COTE_ZONE = 38;
  const TOTAL_ZONE = 20;
  const LEGEND_GAP = 6;
  const legendH = couches.length * 14;
  const bottomH = COTE_ZONE + TOTAL_ZONE + LEGEND_GAP + legendH + 10;
  const svgW = totalW + LEFT_PAD + 70;

  let curX = LEFT_PAD;
  const layerXs = widths.map((w) => {
    const x = curX;
    curX += w + GAP;
    return x;
  });

  return (
    <figure>
      <svg
        viewBox={`0 0 ${svgW} ${LAYER_TOP + LAYER_Y_H + bottomH}`}
        className="w-full max-w-xl"
        role="img"
        aria-label={`Coupe — ${label}`}
      >
        <defs>
          <marker
            id="mc-arr-s"
            markerWidth="7"
            markerHeight="5"
            refX="0"
            refY="2.5"
            orient="auto"
          >
            <path
              d="M7,0 L0,2.5 L7,5"
              fill="none"
              stroke="#E63946"
              strokeWidth="0.8"
            />
          </marker>
          <marker
            id="mc-arr-e"
            markerWidth="7"
            markerHeight="5"
            refX="7"
            refY="2.5"
            orient="auto"
          >
            <path
              d="M0,0 L7,2.5 L0,5"
              fill="none"
              stroke="#E63946"
              strokeWidth="0.8"
            />
          </marker>
          {[...usedNatures].map((n) => (
            <g key={n}>{renderPattern(n)}</g>
          ))}
        </defs>

        {/* Background */}
        <rect
          width={svgW}
          height={LAYER_TOP + LAYER_Y_H + bottomH}
          fill="hsl(220 14% 90%)"
          rx="6"
        />

        {/* Title */}
        <text
          x={svgW / 2}
          y="35"
          textAnchor="middle"
          fontSize="13"
          fill="#2C3E50"
          fontWeight="bold"
        >
          {label}
        </text>

        {/* EXT / INT labels (only for mur_doublage, not cloisons) */}
        {config?.orientation === "horizontal" && schemaType !== "cloison" && (
          <>
            <text
              x={LEFT_PAD - 10}
              y={LAYER_TOP + LAYER_Y_H / 2}
              textAnchor="end"
              fontSize="11"
              fill="#555"
              fontWeight="bold"
            >
              EXT.
            </text>
            <text
              x={layerXs[layerXs.length - 1] + widths[widths.length - 1] + 12}
              y={LAYER_TOP + LAYER_Y_H / 2}
              textAnchor="start"
              fontSize="11"
              fill="#555"
              fontWeight="bold"
            >
              INT.
            </text>
          </>
        )}

        {/* Layers */}
        {couches.map((couche, i) => {
          const x = layerXs[i];
          const w = widths[i];
          const color = NATURE_COLORS[couche.nature] ?? "#ddd";
          const patternId = NATURE_PATTERNS[couche.nature];

          return (
            <g key={i}>
              <rect
                x={x}
                y={LAYER_TOP}
                width={w}
                height={LAYER_Y_H}
                fill={color}
                stroke="#2C3E50"
                strokeWidth="1"
              />
              {patternId && (
                <rect
                  x={x}
                  y={LAYER_TOP}
                  width={w}
                  height={LAYER_Y_H}
                  fill={`url(#${patternId})`}
                />
              )}

              {/* Layer number badge (always visible) */}
              <circle
                cx={x + w / 2}
                cy={LAYER_TOP + 14}
                r="8"
                fill="#2C3E50"
                opacity={0.75}
              />
              <text
                x={x + w / 2}
                y={LAYER_TOP + 18}
                textAnchor="middle"
                fontSize="9"
                fill="#fff"
                fontWeight="bold"
              >
                {i + 1}
              </text>

              {/* Layer name centered inside (only if wide enough for text) */}
              {w > 80 && (
                <foreignObject
                  x={x + 4}
                  y={LAYER_TOP + LAYER_Y_H / 2 - 12}
                  width={w - 8}
                  height={40}
                >
                  <div
                    style={{
                      fontSize: "9px",
                      color: "#2C3E50",
                      fontWeight: "bold",
                      textAlign: "center",
                      lineHeight: "1.2",
                      overflow: "hidden",
                    }}
                  >
                    {couche.nom}
                  </div>
                </foreignObject>
              )}

              {/* Dimension arrow below layer */}
              {(() => {
                const coteTop = LAYER_TOP + LAYER_Y_H + 6;
                const coteLine = coteTop + 8;
                const coteLabel = coteLine + 14;
                return (
                  <>
                    <line
                      x1={x}
                      y1={coteTop}
                      x2={x}
                      y2={coteTop + 16}
                      stroke="#E63946"
                      strokeWidth="0.8"
                    />
                    <line
                      x1={x + w}
                      y1={coteTop}
                      x2={x + w}
                      y2={coteTop + 16}
                      stroke="#E63946"
                      strokeWidth="0.8"
                    />
                    <line
                      x1={x}
                      y1={coteLine}
                      x2={x + w}
                      y2={coteLine}
                      stroke="#E63946"
                      strokeWidth="0.8"
                      markerStart="url(#mc-arr-s)"
                      markerEnd="url(#mc-arr-e)"
                    />
                    <text
                      x={x + w / 2}
                      y={coteLabel}
                      textAnchor="middle"
                      fontSize="9"
                      fill="#E63946"
                      fontWeight="bold"
                    >
                      {couche.epaisseur}
                    </text>
                  </>
                );
              })()}
            </g>
          );
        })}

        {/* Total dimension line */}
        {couches.length > 1 &&
          (() => {
            const firstX = layerXs[0];
            const lastX =
              layerXs[layerXs.length - 1] + widths[widths.length - 1];
            const arrowY = LAYER_TOP + LAYER_Y_H + COTE_ZONE + 10;
            const totalCm = thicknesses
              .reduce((a, b) => a + b, 0)
              .toFixed(1)
              .replace(/\.0$/, "");

            return (
              <g>
                <line
                  x1={firstX}
                  y1={arrowY - 4}
                  x2={firstX}
                  y2={arrowY + 4}
                  stroke="#E63946"
                  strokeWidth="0.8"
                />
                <line
                  x1={lastX}
                  y1={arrowY - 4}
                  x2={lastX}
                  y2={arrowY + 4}
                  stroke="#E63946"
                  strokeWidth="0.8"
                />
                <line
                  x1={firstX}
                  y1={arrowY}
                  x2={lastX}
                  y2={arrowY}
                  stroke="#E63946"
                  strokeWidth="1"
                  markerStart="url(#mc-arr-s)"
                  markerEnd="url(#mc-arr-e)"
                />
                <text
                  x={(firstX + lastX) / 2}
                  y={arrowY - 7}
                  textAnchor="middle"
                  fontSize="9"
                  fill="#E63946"
                  fontWeight="bold"
                >
                  Total : {totalCm} cm
                </text>
              </g>
            );
          })()}

        {/* Legend below — numbered list to avoid overlap */}
        {(() => {
          const legendY =
            LAYER_TOP + LAYER_Y_H + COTE_ZONE + TOTAL_ZONE + LEGEND_GAP;
          return couches.map((couche, i) => (
            <text
              key={`legend-${i}`}
              x={LEFT_PAD}
              y={legendY + i * 14}
              fontSize="9"
              fill="#2C3E50"
            >
              <tspan fontWeight="bold" fill="#2C3E50">
                {i + 1}.
              </tspan>{" "}
              {couche.nom} — {couche.epaisseur}
            </text>
          ));
        })()}
      </svg>

      {extraParams.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-gray-600">
          {extraParams.map(([key, value]) => (
            <li key={key}>
              <span className="font-medium">{key.replace(/_/g, " ")} :</span>{" "}
              {value}
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}
