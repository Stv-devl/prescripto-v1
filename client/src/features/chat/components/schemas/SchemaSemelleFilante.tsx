interface SchemaSemelleFilanteProps {
  params: Record<string, string>;
}

/**
 * SVG parametric cross-section of a strip footing (semelle filante).
 *
 * Layers, bottom to top: blinding concrete, footing, wall, trench walls over
 * hatched soil, ground line. Dimensions read from `params`: B (footing width),
 * H (footing height), `gros_beton` (blinding thickness), `fond_fouille`
 * (trench bottom, absolute level) and `bon_sol` (bearing soil level).
 */
export function SchemaSemelleFilante({ params }: SchemaSemelleFilanteProps) {
  const B = params.B ?? "?";
  const H = params.H ?? "?";
  const grosBeton = params.gros_beton;
  const fondFouille = params.fond_fouille;
  const bonSol = params.bon_sol;

  const tnY = 100;
  const wallLeft = 260;
  const wallRight = 340;
  const semelleLeft = 200;
  const semelleRight = 400;
  const semelleTop = 260;
  const semelleBot = 330;
  const grosBetonBot = 355;
  const fouilleLeft = semelleLeft;
  const fouilleRight = semelleRight;

  return (
    <svg
      viewBox="0 0 650 460"
      className="w-full max-w-md"
      role="img"
      aria-label="Coupe transversale — Semelle filante"
    >
      <defs>
        <marker
          id="sf-arr-s"
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
          id="sf-arr-e"
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
      </defs>

      {/* Backdrop */}
      <rect width="600" height="460" fill="hsl(var(--secondary))" rx="6" />

      {/* Ground level — dashed horizontal line and its label */}
      <line
        x1={wallRight + 10}
        y1={60}
        x2={wallRight + 30}
        y2={60}
        stroke="#2C3E50"
        strokeWidth="1"
        strokeDasharray="4,3"
      />
      <text
        x={wallRight + 35}
        y={64}
        fontSize="11"
        fill="#2C3E50"
        fontWeight="bold"
        textAnchor="start"
      >
        ± 0.00
      </text>

      {/* Natural ground line */}
      <line
        x1="40"
        y1={tnY}
        x2={fouilleLeft}
        y2={tnY}
        stroke="#8B7355"
        strokeWidth="2"
      />
      <line
        x1={fouilleRight}
        y1={tnY}
        x2="560"
        y2={tnY}
        stroke="#8B7355"
        strokeWidth="2"
      />
      <text x="65" y={tnY - 7} fontSize="10" fill="#8B7355">
        TN
      </text>
      <text x="435" y={tnY - 7} fontSize="10" fill="#8B7355">
        TN
      </text>

      {/* Soil hatching — brown diagonals on both sides */}
      {Array.from({ length: 9 }).map((_, i) => {
        const y = tnY + 10 + i * 28;
        return (
          <g key={`hatch-${i}`}>
            <line
              x1={fouilleLeft - 25}
              y1={y}
              x2={fouilleLeft - 5}
              y2={y + 18}
              stroke="#8B7355"
              strokeWidth="0.7"
              opacity={0.4}
            />
            <line
              x1={fouilleRight + 5}
              y1={y}
              x2={fouilleRight + 25}
              y2={y + 18}
              stroke="#8B7355"
              strokeWidth="0.7"
              opacity={0.4}
            />
          </g>
        );
      })}

      {/* Soil mass, translucent fill */}
      <rect
        x={40}
        y={tnY}
        width={fouilleLeft - 40}
        height={grosBetonBot - tnY}
        fill="#D4A574"
        opacity={0.08}
      />
      <rect
        x={fouilleRight}
        y={tnY}
        width={560 - fouilleRight}
        height={grosBetonBot - tnY}
        fill="#D4A574"
        opacity={0.08}
      />

      {/* Trench walls, brown dashes */}
      <line
        x1={fouilleLeft}
        y1={tnY}
        x2={fouilleLeft}
        y2={grosBetonBot}
        stroke="#8B7355"
        strokeWidth="1.2"
        strokeDasharray="5,4"
      />
      <line
        x1={fouilleRight}
        y1={tnY}
        x2={fouilleRight}
        y2={grosBetonBot}
        stroke="#8B7355"
        strokeWidth="1.2"
        strokeDasharray="5,4"
      />

      {/* Wall */}
      <rect
        x={wallLeft}
        y="60"
        width={wallRight - wallLeft}
        height={semelleTop - 60}
        fill="#B0C4DE"
        stroke="#2C3E50"
        strokeWidth="2"
      />
      <text
        x="300"
        y="165"
        textAnchor="middle"
        fontSize="12"
        fill="#2C3E50"
        fontWeight="bold"
      >
        MUR
      </text>

      {/* Footing */}
      <rect
        x={semelleLeft}
        y={semelleTop}
        width={semelleRight - semelleLeft}
        height={semelleBot - semelleTop}
        fill="#A8C5DA"
        stroke="#2C3E50"
        strokeWidth="2.5"
      />
      <text
        x="300"
        y={semelleTop + 40}
        textAnchor="middle"
        fontSize="12"
        fill="#2C3E50"
        fontWeight="bold"
      >
        SEMELLE
      </text>

      {/* Blinding concrete */}
      <rect
        x={semelleLeft}
        y={semelleBot}
        width={semelleRight - semelleLeft}
        height={grosBetonBot - semelleBot}
        fill="#D5D5D5"
        stroke="#2C3E50"
        strokeWidth="1.5"
      />
      <text
        x="300"
        y={semelleBot + 17}
        textAnchor="middle"
        fontSize="10"
        fill="#555"
      >
        BÉTON DE PROPRETÉ
      </text>

      {/* Trench bottom — short rule and its label under the footing */}
      {fondFouille && (
        <g>
          <line
            x1={semelleLeft + 60}
            y1={grosBetonBot}
            x2={semelleRight - 60}
            y2={grosBetonBot}
            stroke="#E63946"
            strokeWidth="0.8"
          />
          <line
            x1="300"
            y1={grosBetonBot}
            x2="300"
            y2={grosBetonBot + 10}
            stroke="#E63946"
            strokeWidth="0.8"
          />
          <text
            x="300"
            y={grosBetonBot + 22}
            textAnchor="middle"
            fontSize="12"
            fill="#E63946"
            fontWeight="bold"
          >
            Fond de fouille : {fondFouille}
          </text>
        </g>
      )}

      {/* Dimension lines */}
      <g fontSize="12" fill="#E63946" fontWeight="bold">
        {/* B — footing width */}
        <line
          x1={semelleLeft}
          y1={grosBetonBot + 56}
          x2={semelleLeft}
          y2={grosBetonBot + 72}
          stroke="#E63946"
          strokeWidth="0.8"
        />
        <line
          x1={semelleRight}
          y1={grosBetonBot + 56}
          x2={semelleRight}
          y2={grosBetonBot + 72}
          stroke="#E63946"
          strokeWidth="0.8"
        />
        <line
          x1={semelleLeft}
          y1={grosBetonBot + 66}
          x2={semelleRight}
          y2={grosBetonBot + 66}
          stroke="#E63946"
          strokeWidth="1"
          markerStart="url(#sf-arr-s)"
          markerEnd="url(#sf-arr-e)"
        />
        <text x="300" y={grosBetonBot + 84} textAnchor="middle">
          B = {B}
        </text>

        {/* H — footing height, on the right */}
        <line
          x1={fouilleRight + 10}
          y1={semelleTop}
          x2={fouilleRight + 30}
          y2={semelleTop}
          stroke="#E63946"
          strokeWidth="0.8"
        />
        <line
          x1={fouilleRight + 10}
          y1={semelleBot}
          x2={fouilleRight + 30}
          y2={semelleBot}
          stroke="#E63946"
          strokeWidth="0.8"
        />
        <line
          x1={fouilleRight + 22}
          y1={semelleTop}
          x2={fouilleRight + 22}
          y2={semelleBot}
          stroke="#E63946"
          strokeWidth="1"
          markerStart="url(#sf-arr-s)"
          markerEnd="url(#sf-arr-e)"
        />
        <text x={fouilleRight + 38} y={semelleTop + 40} textAnchor="start">
          H = {H}
        </text>

        {/* Blinding thickness, on the right, muted */}
        {grosBeton && (
          <>
            <line
              x1={fouilleRight + 10}
              y1={semelleBot}
              x2={fouilleRight + 30}
              y2={semelleBot}
              stroke="#E63946"
              strokeWidth="0.8"
            />
            <line
              x1={fouilleRight + 10}
              y1={grosBetonBot}
              x2={fouilleRight + 30}
              y2={grosBetonBot}
              stroke="#E63946"
              strokeWidth="0.8"
            />
            <line
              x1={fouilleRight + 22}
              y1={semelleBot}
              x2={fouilleRight + 22}
              y2={grosBetonBot}
              stroke="#E63946"
              strokeWidth="1"
              markerStart="url(#sf-arr-s)"
              markerEnd="url(#sf-arr-e)"
            />
            <text x={fouilleRight + 38} y={semelleBot + 17} textAnchor="start">
              {grosBeton}
            </text>
          </>
        )}

        {/* Bearing soil — label */}
        {bonSol && (
          <text
            x="300"
            y={grosBetonBot + 98}
            textAnchor="middle"
            fontSize="10"
            fill="#8B7355"
            fontWeight="normal"
            fontStyle="italic"
          >
            Bon sol : {bonSol}
          </text>
        )}
      </g>
    </svg>
  );
}
