import { motion } from "framer-motion";
import { useState, useEffect } from "react";

interface Step {
  number: number;
  title: string;
  description: string;
}

const STEPS: Step[] = [
  {
    number: 1,
    title: "Uploadez vos documents",
    description:
      "CCTP, comptes-rendus, fiches techniques, DTU, normes CSTB, emails... Glissez-déposez tout. PDF, DOCX, XLSX, DWG, tout est accepté.",
  },
  {
    number: 2,
    title: "Prescripto organise et indexe",
    description:
      "Classement automatique par lot, par phase et par type. Extraction des infos clés. Alerte si des pièces manquent.",
  },
  {
    number: 3,
    title: "Posez vos questions",
    description:
      "« Comment on avait prescrit l'étanchéité sur le projet X ? » Réponse sourcée avec document, page et passage exact. Partagez l'accès à vos prestataires pour qu'ils trouvent l'info eux-mêmes.",
  },
];

const AUTO_PLAY_INTERVAL = 3000;

/**
 * Stats section displaying value-oriented steps with preview.
 */
export function StatsSection(): React.ReactElement {
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % STEPS.length);
    }, AUTO_PLAY_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="relative py-5 md:py-16 overflow-hidden flex justify-center">
      <div className="w-full max-w-[1950px] bg-[#2B2B2B] py-8 md:py-14 mx-4">
        <div className="container px-4">
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 1, ease: "easeOut" }}
          >
            <div className="text-center mb-6 md:mb-16">
              <h2 className="text-xl sm:text-2xl md:text-4xl font-bold text-[#F5F5F5]">
                Opérationnel en 3 minutes
              </h2>
              <p className="text-[#F5F5F5]/60 mt-2 md:mt-4 max-w-2xl mx-auto">
                De la réception du dossier au DCE, Prescripto vous assiste à
                chaque étape
              </p>
            </div>

            <div className="flex flex-col lg:flex-row gap-6 lg:gap-16 items-center justify-center">
              {/* Preview */}
              <motion.div
                className="shrink-0"
                initial={{ opacity: 0, x: -50 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.8, delay: 0.3 }}
              >
                <div className="relative max-w-65 md:max-w-85">
                  {/* Glow effect behind the image */}
                  <div className="absolute -inset-2 md:-inset-4 bg-gradient-to-r from-[#FFC300]/10 via-[#FFC300]/5 to-[#FFC300]/10 rounded-3xl blur-2xl opacity-60" />

                  {/* Card container */}
                  <div className="relative bg-[#2B2B2B] rounded-xl md:rounded-2xl shadow-2xl overflow-hidden">
                    {/* Browser-like header */}
                    <div className="flex items-center gap-2 px-4 py-3 bg-[#1C1C1C]/50">
                      <div className="flex gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-red-400" />
                        <div className="w-3 h-3 rounded-full bg-yellow-400" />
                        <div className="w-3 h-3 rounded-full bg-green-400" />
                      </div>
                      <div className="flex-1 flex justify-center">
                        <div className="px-4 py-1 bg-[#1C1C1C]/50 rounded-md text-xs text-[#F5F5F5]/40">
                          www.prescripto.fr
                        </div>
                      </div>
                    </div>

                    <img
                      src="/dashboard2.webp"
                      alt="Interface Prescripto - Recherche dans les documents projet"
                      className="block w-full h-auto border-0"
                      loading="lazy"
                      decoding="async"
                    />
                  </div>
                </div>
              </motion.div>

              {/* Steps column */}
              <div className="flex flex-col gap-5 md:gap-10 lg:gap-12">
                {STEPS.map((step, index) => {
                  const isActive = index === activeStep;
                  return (
                    <motion.div
                      key={step.number}
                      className="relative flex items-start gap-4 cursor-pointer"
                      initial={{ opacity: 0, x: 20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.5, delay: index * 0.15 }}
                      onClick={() => setActiveStep(index)}
                    >
                      {/* Vertical connector line */}
                      {index < STEPS.length - 1 && (
                        <div className="absolute left-5 top-12 w-0.5 h-full bg-[#F5F5F5]/10 overflow-hidden">
                          <motion.div
                            className="w-full bg-gradient-to-b from-[#FFC300] to-[#FFC300]/70"
                            initial={{ height: "0%" }}
                            animate={{
                              height:
                                activeStep > index
                                  ? "100%"
                                  : activeStep === index
                                    ? "100%"
                                    : "0%",
                            }}
                            transition={{
                              duration:
                                activeStep === index
                                  ? AUTO_PLAY_INTERVAL / 1000
                                  : 0.3,
                              ease: activeStep === index ? "linear" : "easeOut",
                            }}
                            key={
                              activeStep === index
                                ? `filling-${activeStep}`
                                : `static-${index}`
                            }
                          />
                        </div>
                      )}

                      {/* Circle with number */}
                      <motion.div
                        className="w-10 h-10 shrink-0 rounded-full flex items-center justify-center text-[#1C1C1C] font-bold text-sm relative z-10"
                        animate={{
                          scale: isActive ? 1.15 : 1,
                          boxShadow: isActive
                            ? "0 0 20px rgba(255, 195, 0, 0.4)"
                            : "0 0 0px rgba(255, 195, 0, 0)",
                        }}
                        transition={{ duration: 0.3 }}
                        style={{
                          background:
                            "linear-gradient(135deg, #FFC300 0%, #E6B000 100%)",
                        }}
                      >
                        {step.number}
                      </motion.div>

                      {/* Content */}
                      <motion.div
                        className="flex-1 pt-1"
                        animate={{
                          opacity: isActive ? 1 : 0.6,
                          x: isActive ? 4 : 0,
                        }}
                        transition={{ duration: 0.3 }}
                      >
                        <h3 className="text-lg font-semibold mb-1 text-[#F5F5F5]">
                          {step.title}
                        </h3>
                        <p className="text-[#F5F5F5]/60 text-sm max-w-xs">
                          {step.description}
                        </p>
                      </motion.div>

                      {/* Active indicator glow */}
                      {isActive && (
                        <motion.div
                          className="absolute -inset-2 bg-[#FFC300]/5 rounded-xl -z-10"
                          layoutId="activeStepBg"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          transition={{ duration: 0.3 }}
                        />
                      )}
                    </motion.div>
                  );
                })}
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
