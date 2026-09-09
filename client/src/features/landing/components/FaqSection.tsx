import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";
import * as React from "react";
import type { FaqItem } from "../types/types";

const FAQ_ITEMS: FaqItem[] = [
  {
    question: "Quels formats de documents puis-je importer ?",
    answer:
      "CCTP, comptes-rendus, fiches techniques, DTU, normes CSTB, plans, estimatifs… Prescripto ingère vos PDF, DOCX, XLSX et DWG. Glissez-déposez votre dossier projet : il est analysé et indexé en quelques minutes.",
  },
  {
    question: "Mes données restent-elles confidentielles ?",
    answer:
      "Absolument. Infrastructure 100 % souveraine : IA Mistral hébergée à Paris, serveurs en France, zéro transit hors UE. Chaque cabinet dispose d'un espace cloisonné — vos dossiers ne sont jamais accessibles par un autre utilisateur.",
  },
  {
    question: "Combien de temps faut-il pour démarrer ?",
    answer:
      "Moins de 5 minutes. Créez votre compte, importez les documents d'un projet et posez votre première question. Pas de formation, pas de paramétrage complexe — l'IA s'adapte à vos documents.",
  },
  {
    question: "L'IA va-t-elle remplacer mon expertise ?",
    answer:
      "Non, elle l'amplifie. Prescripto retrouve en secondes ce que vous chercheriez en heures dans vos archives. L'IA propose des réponses sourcées, vous gardez le dernier mot. Votre savoir-faire reste au centre de chaque décision.",
  },
  {
    question: "Comment l'IA retrouve-t-elle la bonne information ?",
    answer:
      "Prescripto découpe chaque document, en comprend le sens grâce à l'IA, puis croise vos questions avec les passages les plus pertinents. Chaque réponse cite la source exacte : nom du document, page et extrait. Vous vérifiez en un clic.",
  },
  {
    question: "Puis-je collaborer avec mes partenaires sur un projet ?",
    answer:
      "Oui. Invitez sous-traitants, bureaux d'études ou de contrôle directement depuis votre espace projet. Définissez des droits d'accès précis : consultation seule, recherche ou accès complet. Vous restez maître du dossier.",
  },
  {
    question: "Que se passe-t-il si je veux arrêter ?",
    answer:
      "Rien de compliqué. Résiliez en deux clics depuis votre compte. Votre accès reste actif jusqu'à la fin de la période en cours, et vous pouvez exporter vos données à tout moment. Zéro engagement, zéro frais cachés.",
  },
];

interface FaqItemComponentProps {
  item: FaqItem;
  isOpen: boolean;
  onToggle: () => void;
}

function FaqItemComponent({
  item,
  isOpen,
  onToggle,
}: FaqItemComponentProps): React.ReactElement {
  return (
    <div className="bg-[#2B2B2B] rounded-lg border border-[#F5F5F5]/10 overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between p-4 lg:p-6 text-left font-medium text-[#F5F5F5] transition-colors hover:text-[#FFC300] cursor-pointer"
        aria-expanded={isOpen}
      >
        <span className="text-sm md:text-base pr-4">{item.question}</span>
        <motion.div
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2, ease: "easeInOut" }}
          className="shrink-0"
        >
          <ChevronDown className="h-5 w-5 text-[#F5F5F5]/40" />
        </motion.div>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
          >
            <div className="px-4 lg:px-6 pb-4 lg:pb-6 text-sm lg:text-base text-[#F5F5F5]/60 leading-relaxed">
              {item.answer}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * FAQ section with title on the left and accordion on the right.
 */
export function FaqSection(): React.ReactElement {
  const [openIndex, setOpenIndex] = React.useState<number | null>(null);

  const handleToggle = (index: number): void => {
    setOpenIndex(openIndex === index ? null : index);
  };

  return (
    <section className="py-5 md:py-20 bg-[#1C1C1C]">
      <div className="container px-4">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row md:gap-16 lg:gap-24">
          {/* Left — Title + subtitle */}
          <motion.div
            className="md:w-1/3 shrink-0 mb-8 md:mb-0 md:sticky md:top-24 md:self-start space-y-3 md:space-y-4"
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.7, ease: "easeOut" }}
          >
            <h2 className="text-xl sm:text-2xl md:text-4xl font-bold text-[#F5F5F5]">
              Vos questions, nos réponses
            </h2>
            <p className="text-[#F5F5F5]/60 text-sm md:text-base leading-relaxed">
              Sécurité, formats, collaboration, tarifs… On répond aux questions
              que vous vous posez avant de vous lancer. Et si la vôtre n'y est
              pas, notre équipe est là.
            </p>
          </motion.div>

          {/* Right — Accordion */}
          <motion.div
            className="md:w-2/3 space-y-3"
            initial={{ opacity: 0, x: 40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.7, ease: "easeOut", delay: 0.1 }}
          >
            {FAQ_ITEMS.map((item, index) => (
              <FaqItemComponent
                key={index}
                item={item}
                isOpen={openIndex === index}
                onToggle={() => handleToggle(index)}
              />
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  );
}
