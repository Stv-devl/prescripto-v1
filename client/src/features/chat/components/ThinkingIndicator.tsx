import { useEffect, useState } from "react";

const MESSAGES = [
  "Analyse des documents…",
  "Recherche dans le CCTP…",
  "Lecture des pièces techniques…",
  "Croisement des sources…",
  "Vérification des données…",
  "Extraction des informations…",
  "Synthèse en cours…",
];

function pickRandom(exclude: number): number {
  let next: number;
  do {
    next = Math.floor(Math.random() * MESSAGES.length);
  } while (next === exclude && MESSAGES.length > 1);
  return next;
}

export function ThinkingIndicator() {
  const [index, setIndex] = useState(() =>
    Math.floor(Math.random() * MESSAGES.length),
  );
  const [fade, setFade] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setFade(false);
      setTimeout(() => {
        setIndex((prev) => pickRandom(prev));
        setFade(true);
      }, 200);
    }, 2800);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <div className="flex gap-1" aria-hidden="true">
        <span className="thinking-dot" />
        <span className="thinking-dot [animation-delay:0.2s]" />
        <span className="thinking-dot [animation-delay:0.4s]" />
      </div>
      <span
        className={`text-sm text-muted-foreground transition-opacity duration-200 ${
          fade ? "opacity-100" : "opacity-0"
        }`}
      >
        {MESSAGES[index]}
      </span>
    </div>
  );
}
