interface SchemaFouilleRigoleProps {
  params: Record<string, string>;
}

/**
 * SVG parametric cross-section of a trench excavation (fouille en rigole).
 * Pure excavation profile — terrain, parois, fond, hachures.
 * Cotations: largeur, profondeur.
 */
export function SchemaFouilleRigole({ params }: SchemaFouilleRigoleProps) {
  const largeur = params.largeur ?? "?";
  const profondeur = params.profondeur ?? "?";

  const cx = 250;
  const tnY = 90;
  const trenchW = 160;
  const trenchH = 200;
  const fondY = tnY + trenchH;

  return (
    <svg
      viewBox="0 0 500 350"
      className="w-full max-w-sm"
      role="img"
      aria-label="Coupe transversale — Fouille en rigole"
    >
      <defs>
        <marker id="fr-arr-s" markerWidth="7" markerHeight="5" refX="0" refY="2.5" orient="auto">
          <path d="M7,0 L0,2.5 L7,5" fill="none" stroke="#E63946" strokeWidth="0.8" />
        </marker>
        <marker id="fr-arr-e" markerWidth="7" markerHeight="5" refX="7" refY="2.5" orient="auto">
          <path d="M0,0 L7,2.5 L0,5" fill="none" stroke="#E63946" strokeWidth="0.8" />
        </marker>
      </defs>

      {/* Fond */}
      <rect width="500" height="350" fill="hsl(var(--secondary))" rx="6" />

      {/* Masse de terre */}
      <rect x={30} y={tnY} width={cx - trenchW / 2 - 30} height={trenchH} fill="#D4A574" opacity={0.15} />
      <rect x={cx + trenchW / 2} y={tnY} width={470 - cx - trenchW / 2} height={trenchH} fill="#D4A574" opacity={0.15} />

      {/* Terrain naturel */}
      <line x1="30" y1={tnY} x2={cx - trenchW / 2} y2={tnY} stroke="#8B7355" strokeWidth="2.5" />
      <line x1={cx + trenchW / 2} y1={tnY} x2="470" y2={tnY} stroke="#8B7355" strokeWidth="2.5" />
      <text x="45" y={tnY - 8} fontSize="11" fill="#8B7355" fontWeight="bold">TN</text>
      <text x="440" y={tnY - 8} fontSize="11" fill="#8B7355" fontWeight="bold">TN</text>

      {/* Parois fouille */}
      <line x1={cx - trenchW / 2} y1={tnY} x2={cx - trenchW / 2} y2={fondY} stroke="#5C4033" strokeWidth="2" />
      <line x1={cx + trenchW / 2} y1={tnY} x2={cx + trenchW / 2} y2={fondY} stroke="#5C4033" strokeWidth="2" />

      {/* Fond de fouille */}
      <line x1={cx - trenchW / 2} y1={fondY} x2={cx + trenchW / 2} y2={fondY} stroke="#5C4033" strokeWidth="2" />

      {/* Hachures terre */}
      {Array.from({ length: 7 }).map((_, i) => {
        const y = tnY + 15 + i * 28;
        return (
          <g key={i}>
            <line x1={cx - trenchW / 2 - 20} y1={y} x2={cx - trenchW / 2 - 5} y2={y + 15} stroke="#8B7355" strokeWidth="0.7" opacity={0.35} />
            <line x1={cx + trenchW / 2 + 5} y1={y} x2={cx + trenchW / 2 + 20} y2={y + 15} stroke="#8B7355" strokeWidth="0.7" opacity={0.35} />
          </g>
        );
      })}

      {/* Label fouille */}
      <text x={cx} y={tnY + trenchH / 2} textAnchor="middle" fontSize="11" fill="#8B7355" opacity={0.5}>fouille</text>

      {/* Cotations */}
      <g fontSize="11" fill="#E63946" fontWeight="bold">
        {/* Largeur fouille */}
        <line x1={cx - trenchW / 2} y1={fondY + 12} x2={cx - trenchW / 2} y2={fondY + 28} stroke="#E63946" strokeWidth="0.8" />
        <line x1={cx + trenchW / 2} y1={fondY + 12} x2={cx + trenchW / 2} y2={fondY + 28} stroke="#E63946" strokeWidth="0.8" />
        <line x1={cx - trenchW / 2} y1={fondY + 22} x2={cx + trenchW / 2} y2={fondY + 22} stroke="#E63946" strokeWidth="1" markerStart="url(#fr-arr-s)" markerEnd="url(#fr-arr-e)" />
        <text x={cx} y={fondY + 40} textAnchor="middle">{largeur}</text>

        {/* Profondeur fouille */}
        <line x1={cx - trenchW / 2 - 28} y1={tnY} x2={cx - trenchW / 2 - 42} y2={tnY} stroke="#E63946" strokeWidth="0.8" />
        <line x1={cx - trenchW / 2 - 28} y1={fondY} x2={cx - trenchW / 2 - 42} y2={fondY} stroke="#E63946" strokeWidth="0.8" />
        <line x1={cx - trenchW / 2 - 37} y1={tnY} x2={cx - trenchW / 2 - 37} y2={fondY} stroke="#E63946" strokeWidth="1" markerStart="url(#fr-arr-s)" markerEnd="url(#fr-arr-e)" />
        <text x={cx - trenchW / 2 - 44} y={tnY + trenchH / 2 + 4} textAnchor="end" fontSize="10">{profondeur}</text>
      </g>
    </svg>
  );
}
