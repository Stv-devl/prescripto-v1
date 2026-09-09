import { motion } from "framer-motion";
import {
  Search,
  FolderOpen,
  MessageSquare,
  Layers,
  Users,
  ShieldCheck,
} from "lucide-react";
import type { Feature } from "../types/types";

const FEATURES: Feature[] = [
  {
    icon: Search,
    title: "Recherche intelligente",
    description:
      "Posez vos questions en langage courant : « Quel Uw est exigé ? », « Comment on avait prescrit l'étanchéité sur le projet X ? ». Réponse immédiate avec document, page et passage exact.",
  },
  {
    icon: FolderOpen,
    title: "Classement automatique",
    description:
      "Chaque document uploadé est classé par type (CCTP, CR, fiche technique, DTU…), par lot et par phase. Fini le rangement manuel.",
  },
  {
    icon: MessageSquare,
    title: "Chat projet",
    description:
      "Résumez un rapport acoustique, comparez deux CCTP, extrayez les matériaux prescrits sur un lot.",
  },
  {
    icon: Layers,
    title: "Vue multi-projets",
    description:
      "Passez d'un chantier à l'autre en un clic. Chaque projet reste cloisonné avec ses documents et conversations.",
  },
  {
    icon: Users,
    title: "Collaboration",
    description:
      "Invitez un prestataire ou un collègue sur un projet. Il accède uniquement à ce que vous partagez.",
  },
  {
    icon: ShieldCheck,
    title: "Conformité DTU & normes",
    description:
      "Vérifiez en un instant si vos prescriptions respectent les DTU et normes CSTB en vigueur. Prescripto vous signale les écarts.",
  },
];

/** Grid positions for each card (desktop: 4-column grid, 3+3) */
const GRID_POSITIONS = [
  "md:col-span-2",
  "",
  "",
  "",
  "",
  "md:col-span-2",
] as const;

interface FeatureCardProps {
  feature: Feature;
  index: number;
  isLarge: boolean;
}

function FeatureCard({
  feature,
  index,
  isLarge,
}: FeatureCardProps): React.ReactElement {
  const Icon = feature.icon;

  return (
    <motion.article
      className={`relative group ${GRID_POSITIONS[index]}`}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5, delay: index * 0.07 }}
    >
      {/* Glow */}
      <div className="absolute -inset-1 bg-gradient-to-r from-[#FFC300]/20 via-[#FFC300]/10 to-[#FFC300]/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-60 transition-opacity duration-500" />

      {/* Card */}
      <div
        className={`relative h-full bg-[#2B2B2B] backdrop-blur-xl rounded-2xl border border-[#F5F5F5]/10 shadow-xl ${isLarge ? "p-6 md:p-8 md:py-10" : "p-5 md:p-6 md:py-8"}`}
      >
        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-br from-[#FFC300]/5 via-transparent to-[#FFC300]/3 pointer-events-none rounded-2xl" />

        {/* Content */}
        <div className="relative space-y-3">
          <div className="flex items-center gap-3">
            <div className="relative shrink-0">
              <div className="absolute -inset-1 bg-gradient-to-r from-[#FFC300] to-[#FFD54F] rounded-xl opacity-50 group-hover:opacity-80 transition-opacity duration-300" />
              <div
                className={`relative rounded-xl bg-gradient-to-br from-[#FFC300] to-[#E6B000] flex items-center justify-center ${isLarge ? "w-11 h-11 md:w-12 md:h-12" : "w-9 h-9 md:w-10 md:h-10"}`}
              >
                <Icon
                  className={`text-[#1C1C1C] ${isLarge ? "h-5 w-5 md:h-6 md:w-6" : "h-4 w-4 md:h-5 md:w-5"}`}
                />
              </div>
            </div>
            <h3
              className={`font-semibold text-[#F5F5F5] ${isLarge ? "text-lg md:text-xl" : "text-base md:text-lg"}`}
            >
              {feature.title}
            </h3>
          </div>

          <p className="text-[#F5F5F5]/60 text-sm md:text-base leading-relaxed">
            {feature.description}
          </p>
        </div>
      </div>
    </motion.article>
  );
}

/**
 * Features section displaying capabilities in a 2-row asymmetric grid.
 * First card (top-left) and last card (bottom-right) span 2 columns.
 */
export function FeaturesSection(): React.ReactElement {
  return (
    <section
      id="features-section"
      className="relative py-8 md:py-20 flex justify-center"
    >
      <div className="w-full max-w-7xl px-4 md:px-8">
        <motion.div
          className="text-center space-y-2 mb-8 md:mb-14"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        >
          <h2 className="text-xl sm:text-2xl md:text-4xl font-bold text-[#F5F5F5]">
            La mémoire de vos projets, accessible en un clic
          </h2>
          <p className="text-[#F5F5F5]/60 max-w-2xl mx-auto">
            Uploadez vos dossiers. Prescripto les comprend, les organise et
            répond à vos questions.
          </p>
        </motion.div>

        {/* Grid: 5 columns on desktop, 2 on tablet, 1 on mobile */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 md:gap-5">
          {FEATURES.map((feature, index) => (
            <FeatureCard
              key={feature.title}
              feature={feature}
              index={index}
              isLarge={index === 0 || index === FEATURES.length - 1}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
