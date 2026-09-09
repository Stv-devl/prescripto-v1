import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Quote } from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import type { Testimonial } from "../types/types";
import { Rating } from "./Rating";

const TESTIMONIALS: Testimonial[] = [
  {
    name: "Claire Morel",
    role: "Économiste de la construction",
    quote:
      "Je retrouve en 30 secondes une info qui me prenait 2 heures à chercher dans mes anciens CCTP. Indispensable dès la phase APS.",
    image: "/pexels-olly-774909.webp",
    rating: 5,
  },
  {
    name: "Marc Lefebvre",
    role: "Directeur BET économie",
    quote:
      "On a divisé par 3 le temps de rédaction du DCE. L'outil ressort les bonnes prescriptions de nos anciens projets automatiquement.",
    image: "/pexels-simon-robben-55958-614810.webp",
    rating: 5,
  },
  {
    name: "Julie Garnier",
    role: "Architecte DPLG",
    quote:
      "La recherche dans les comptes-rendus de réunion est bluffante. Plus aucune décision ne se perd entre les phases.",
    image: "/pexels-olly-733872.webp",
    rating: 5,
  },
  {
    name: "Antoine Durand",
    role: "Maître d'oeuvre",
    quote:
      "Je partage l'accès au dossier avec mes sous-traitants. Ils trouvent les infos eux-mêmes sans m'appeler toutes les 5 minutes.",
    image:
      "/cheerful-positive-young-european-woman-with-dark-hair-broad-shining-smile-points-with-thumb-aside1.webp",
    rating: 5,
  },
  {
    name: "Philippe Renaud",
    role: "Ingénieur structure",
    quote:
      "Pouvoir interroger tous les documents d'un projet en langage naturel, c'est exactement ce qu'il nous manquait.",
    image: "/person-1.webp",
    rating: 5,
  },
  {
    name: "Sarah Ben Ali",
    role: "Économiste junior",
    quote:
      "En tant que junior, c'est mon meilleur outil d'apprentissage. Je consulte les anciens CCTP du cabinet en un clic.",
    image: "/person-2.webp",
    rating: 5,
  },
];

const AUTO_PLAY_INTERVAL = 4000;

interface TestimonialCardProps {
  testimonial: Testimonial;
  isActive: boolean;
  position: number;
}

/**
 * One testimonial in the carousel.
 *
 * Exported for its tests only: nothing outside this feature may import it, and
 * `features/landing/index.ts` does not re-export it.
 */
export function TestimonialCard({
  testimonial,
  isActive,
  position,
}: TestimonialCardProps): React.ReactElement {
  return (
    <motion.div
      aria-hidden={!isActive}
      className="absolute top-0 w-75 md:w-95"
      initial={false}
      animate={{
        x: `calc(${position * 100}% + ${position * 24}px)`,
        scale: isActive ? 1 : 0.85,
        opacity: Math.abs(position) <= 1 ? (isActive ? 1 : 0.5) : 0,
        zIndex: isActive ? 10 : 5 - Math.abs(position),
      }}
      transition={{
        duration: 0.6,
        ease: [0.32, 0.72, 0, 1],
      }}
    >
      <div className="relative group">
        {/* Glow effect */}
        <div
          className={`absolute -inset-1 bg-gradient-to-r from-[#FFC300]/30 via-[#FFC300]/20 to-[#FFC300]/30 rounded-3xl blur-xl transition-opacity duration-500 ${
            isActive ? "opacity-60" : "opacity-0"
          }`}
        />

        {/* Card */}
        <div className="relative bg-[#2B2B2B] backdrop-blur-xl rounded-3xl p-5 md:p-8 border border-[#F5F5F5]/10 shadow-2xl overflow-hidden">
          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-br from-[#FFC300]/5 via-transparent to-[#FFC300]/3 pointer-events-none" />

          {/* Quote icon */}
          <div className="absolute -top-2 -right-2 opacity-10">
            <Quote className="h-24 w-24 text-[#FFC300]" />
          </div>

          {/* Content */}
          <div className="relative space-y-4 md:space-y-6">
            {/* Author at top */}
            <div className="flex items-center gap-4">
              <div className="relative">
                <div
                  className={`absolute -inset-1 bg-gradient-to-r from-[#FFC300] to-[#FFD54F] rounded-full transition-opacity duration-300 ${
                    isActive ? "opacity-100" : "opacity-50"
                  }`}
                />
                <div className="relative w-14 h-14 md:w-16 md:h-16 rounded-full overflow-hidden ring-2 ring-[#2B2B2B]">
                  <img
                    src={testimonial.image}
                    alt={testimonial.name}
                    className="w-full h-full object-cover"
                    loading="lazy"
                    decoding="async"
                  />
                </div>
              </div>
              <div>
                <p className="font-bold text-[#F5F5F5] text-lg">
                  {testimonial.name}
                </p>
                <p className="text-sm text-[#FFC300] font-medium">
                  {testimonial.role}
                </p>
              </div>
            </div>

            {/* Quote text */}
            <p className="text-[#F5F5F5]/60 text-sm md:text-base leading-relaxed">
              "{testimonial.quote}"
            </p>

            {/* Rating */}
            <Rating value={testimonial.rating} />
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/**
 * Testimonials section with infinite carousel.
 */
export function TestimonialsSection(): React.ReactElement {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  const totalItems = TESTIMONIALS.length;

  const goToPrevious = useCallback((): void => {
    setCurrentIndex((prev) => (prev === 0 ? totalItems - 1 : prev - 1));
  }, [totalItems]);

  const goToNext = useCallback((): void => {
    setCurrentIndex((prev) => (prev === totalItems - 1 ? 0 : prev + 1));
  }, [totalItems]);

  useEffect(() => {
    if (isPaused) return;

    const interval = setInterval(goToNext, AUTO_PLAY_INTERVAL);
    return () => clearInterval(interval);
  }, [isPaused, goToNext]);

  const getPosition = (index: number): number => {
    let diff = index - currentIndex;
    if (diff > totalItems / 2) diff -= totalItems;
    if (diff < -totalItems / 2) diff += totalItems;
    return diff;
  };

  return (
    <section className="relative py-5 md:py-24 overflow-hidden">
      <div className="container px-4 relative z-10">
        <motion.div
          className="text-center space-y-1 mb-1"
          initial={{ opacity: 0, x: 60 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        >
          <h2 className="text-xl sm:text-2xl md:text-4xl font-bold text-[#F5F5F5]">
            Ils retrouvent l'info en secondes au lieu d'heures
          </h2>
          <p className="text-[#F5F5F5]/60 max-w-2xl mx-auto">
            Découvrez comment Prescripto accélère la conception
          </p>
        </motion.div>

        {/* Carousel */}
        <div
          className="relative"
          onMouseEnter={() => setIsPaused(true)}
          onMouseLeave={() => setIsPaused(false)}
        >
          <div className="relative h-80 md:h-95 flex items-start justify-center pt-4 mt-5 md:mt-7.5">
            <div className="relative w-75 md:w-95">
              {TESTIMONIALS.map((testimonial, index) => {
                const position = getPosition(index);
                return (
                  <TestimonialCard
                    key={testimonial.name}
                    testimonial={testimonial}
                    isActive={index === currentIndex}
                    position={position}
                  />
                );
              })}
            </div>
          </div>

          {/* Navigation */}
          <div className="flex items-center justify-center gap-8 -mt-8 md:-mt-4 relative z-30">
            <button
              onClick={goToPrevious}
              className="group cursor-pointer"
              aria-label="Témoignage précédent"
            >
              <div className="flex items-center justify-center w-10 h-10 md:w-16 md:h-16 rounded-full bg-[#2B2B2B] border-2 border-[#FFC300]/20 shadow-xl group-hover:shadow-2xl group-hover:border-[#FFC300] group-hover:bg-[#FFC300]/5 transition-all duration-300 group-active:scale-90">
                <ChevronLeft className="h-5 w-5 md:h-8 md:w-8 text-[#FFC300]" />
              </div>
            </button>

            <button
              onClick={goToNext}
              className="group cursor-pointer"
              aria-label="Témoignage suivant"
            >
              <div className="flex items-center justify-center w-10 h-10 md:w-16 md:h-16 rounded-full bg-[#2B2B2B] border-2 border-[#FFC300]/20 shadow-xl group-hover:shadow-2xl group-hover:border-[#FFC300] group-hover:bg-[#FFC300]/5 transition-all duration-300 group-active:scale-90">
                <ChevronRight className="h-5 w-5 md:h-8 md:w-8 text-[#FFC300]" />
              </div>
            </button>
          </div>

          {/* Dots indicator */}
          <div className="flex items-center justify-center gap-3 mt-3 md:mt-6">
            {TESTIMONIALS.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentIndex(index)}
                className="group relative p-1"
                aria-label={`Aller au témoignage ${index + 1}`}
              >
                <motion.div
                  className="relative"
                  animate={{
                    scale: index === currentIndex ? 1 : 0.8,
                  }}
                  transition={{ duration: 0.2 }}
                >
                  <div
                    className={`w-3 h-3 rounded-full transition-all duration-300 ${
                      index === currentIndex
                        ? "bg-gradient-to-r from-[#FFC300] to-[#FFD54F] shadow-lg shadow-[#FFC300]/30"
                        : "bg-[#F5F5F5]/20 group-hover:bg-[#F5F5F5]/40"
                    }`}
                  />
                  {index === currentIndex && (
                    <motion.div
                      className="absolute inset-0 bg-gradient-to-r from-[#FFC300] to-[#FFD54F] rounded-full"
                      layoutId="activeDot"
                      transition={{
                        type: "spring",
                        stiffness: 300,
                        damping: 30,
                      }}
                    />
                  )}
                </motion.div>
              </button>
            ))}
          </div>

          {/* Auto-play progress bar */}
          <div className="max-w-50 mx-auto mt-2 md:mt-4">
            <div className="h-1 bg-[#F5F5F5]/10 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-[#FFC300] to-[#FFD54F]"
                initial={{ scaleX: 0 }}
                animate={{ scaleX: isPaused ? 0 : 1 }}
                transition={{
                  duration: isPaused ? 0 : AUTO_PLAY_INTERVAL / 1000,
                  ease: "linear",
                }}
                style={{ transformOrigin: "left" }}
                key={currentIndex}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
