"""Chat prompts, constants, and keyword patterns."""

import re

# ── Numeric constants ─────────────────────────────────────────────

HISTORY_WINDOW = 6
CONTEXT_MAX_CHARS = 20000
SOURCE_SCORE_THRESHOLD = 0.50
MAX_DISPLAYED_SOURCES = 5
MIN_SOURCE_TEXT_LENGTH = 80

# ── Schema types ──────────────────────────────────────────────────

SCHEMA_TYPES: dict[str, list[str]] = {
    "semelle_filante": ["B", "H", "gros_beton", "fond_fouille", "bon_sol"],
    "fouille_rigole": ["largeur", "profondeur"],
    "semelle_isolee": ["poteau_a", "poteau_b", "A", "B", "H", "gros_beton"],
    "dallage_terre_plein": ["couches", "epaisseur_totale"],
    "plancher_hourdis": ["couches", "type_poutrelle", "entraxe"],
    "plancher_bois": ["couches", "type_solivage", "entraxe", "section_solivage"],
    "toiture_terrasse": ["couches", "type_toiture"],
    "mur_doublage": ["couches", "type_isolation"],
    "cloison": ["couches", "type_cloison"],
    "charpente_couverture": ["couches", "type_couverture"],
    "voirie": ["couches", "classe_trafic"],
    "coupe_geotechnique": [
        "couches",
        "niveau_nappe",
        "profondeur_bon_sol",
        "portance",
        "nature_bon_sol",
    ],
}

# ── Schema extraction prompt ─────────────────────────────────────

SCHEMA_EXTRACTION_PROMPT = (
    "Tu es un expert en économie de la construction. "
    "À partir du contexte documentaire et de la question, identifie si un schéma "
    "technique en coupe est pertinent et extrais les paramètres dimensionnels.\n\n"
    "Types de schémas disponibles :\n"
    + "\n".join(f"- {k} (params: {', '.join(v)})" for k, v in SCHEMA_TYPES.items())
    + "\n\n"
    "Règles :\n"
    "1. CHOIX DU TYPE — Choisis UN SEUL type. "
    "Analyse d'abord la QUESTION pour comprendre quel ouvrage est demandé, "
    "puis cherche cet ouvrage dans le contexte. "
    "HIÉRARCHIE de priorité pour les planchers :\n"
    "   - 'solivage', 'plancher bois', 'OSB sur solivage' → plancher_bois "
    "(si le CCTP mentionne solivage bois, panneaux OSB, lamellé-collé)\n"
    "   - 'plancher bas', 'plancher RDC', 'plancher du RDC' → plancher_hourdis "
    "(si le CCTP mentionne poutrelles/entrevous/hourdis)\n"
    "   - 'dallage', 'terre-plein', 'garage' → dallage_terre_plein\n"
    "   NE JAMAIS choisir plancher_hourdis pour un plancher bois (solivage + OSB). "
    "plancher_hourdis = poutrelles béton + entrevous + dalle de répartition. "
    "plancher_bois = solivage bois + panneaux OSB/dérivés.\n"
    "   NE JAMAIS choisir dallage_terre_plein pour décrire le plancher habitable "
    "du RDC si le CCTP décrit un plancher hourdis (poutrelles + entrevous + dalle). "
    "Le dallage sur terre-plein est réservé aux garages, terrasses et locaux annexes.\n"
    "2. Extrais les valeurs UNIQUEMENT depuis le contexte.\n"
    "3. Si un paramètre n'est pas trouvé, ne l'inclus PAS dans params.\n"
    "4. IMPORTANT — Pour semelle_filante, cherche TOUJOURS ces infos :\n"
    "   - fond_fouille : cote du fond de la FOUILLE EN RIGOLE (pas la plateforme "
    "ni le terrassement général). C'est le niveau le plus bas, sous les semelles. "
    "Cherche 'fouille en rigole', 'cote fond de fouille en rigole'. "
    "La fouille en rigole est TOUJOURS plus profonde que la plateforme.\n"
    "   - bon_sol : nature ou profondeur du sol porteur "
    "(cherche 'bon sol', 'sol porteur', 'argile', 'grave')\n"
    "   Ces paramètres peuvent être des descriptions courtes.\n"
    "5. IMPORTANT — Pour les schémas multicouches (dallage_terre_plein, plancher_hourdis, "
    "plancher_bois, toiture_terrasse, mur_doublage, cloison, charpente_couverture, voirie) :\n"
    "   - couches : JSON array des couches de l'ouvrage, TOUJOURS DU HAUT VERS LE BAS "
    "(la couche visible/finition en PREMIER, le support/structure en DERNIER). "
    "Pour un plancher : carrelage → chape → isolant → dalle → structure. "
    "Pour un dallage : carrelage → chape → dalle béton → isolant → film → gravier → tout-venant. "
    "Pour un mur : intérieur → extérieur (gauche → droite).\n"
    '     Chaque couche = {"nom": "...", "epaisseur": "... cm", "nature": "..."}\n'
    "     Natures valides : beton, beton_arme, chape, mortier, isolant_thermique, "
    "isolant_acoustique, etancheite, pare_vapeur, film_pe, revetement, carrelage, "
    "enduit, plaque_platre, bois, metal, gravier, enrobe, grave, hourdis, "
    "geotextile, tuile, ecran_sous_toiture, ossature_isolant\n"
    "   - Épaisseurs en cm (ex: '5 cm', '12 cm'). "
    "JAMAIS 'non précisée', 'inconnue' ou vide. "
    "Si l'épaisseur d'une couche n'est pas dans le contexte, NE L'INCLUS PAS dans les couches.\n"
    "   - Extrais les couches UNIQUEMENT depuis le contexte documentaire.\n"
    "   Exemples :\n"
    '   dallage_terre_plein : {"schema_type": "dallage_terre_plein", '
    '"title": "Dallage sur terre-plein", "params": {"couches": '
    '"[{\\"nom\\":\\"Carrelage\\",\\"epaisseur\\":\\"1 cm\\",\\"nature\\":\\"carrelage\\"},'
    '{\\"nom\\":\\"Chape\\",\\"epaisseur\\":\\"5 cm\\",\\"nature\\":\\"chape\\"},'
    '{\\"nom\\":\\"Dallage BA\\",\\"epaisseur\\":\\"15 cm\\",\\"nature\\":\\"beton_arme\\"},'
    '{\\"nom\\":\\"Isolant XPS\\",\\"epaisseur\\":\\"8 cm\\",\\"nature\\":\\"isolant_thermique\\"},'
    '{\\"nom\\":\\"Polyane 150 µm\\",\\"epaisseur\\":\\"0.2 cm\\",\\"nature\\":\\"film_pe\\"},'
    '{\\"nom\\":\\"Sable de pose\\",\\"epaisseur\\":\\"5 cm\\",\\"nature\\":\\"gravier\\"},'
    '{\\"nom\\":\\"Tout-venant compacté\\",\\"epaisseur\\":\\"20 cm\\",\\"nature\\":\\"gravier\\"}]", '
    '"epaisseur_totale": "54 cm"}}\n'
    '   plancher_hourdis : {"schema_type": "plancher_hourdis", '
    '"title": "Plancher hourdis RDC", "params": {"couches": '
    '"[{\\"nom\\":\\"Carrelage grès cérame\\",\\"epaisseur\\":\\"1 cm\\",\\"nature\\":\\"carrelage\\"},'
    '{\\"nom\\":\\"Chape armée\\",\\"epaisseur\\":\\"6 cm\\",\\"nature\\":\\"chape\\"},'
    '{\\"nom\\":\\"Isolant polyuréthane\\",\\"epaisseur\\":\\"10 cm\\",\\"nature\\":\\"isolant_thermique\\"},'
    '{\\"nom\\":\\"Dalle de répartition\\",\\"epaisseur\\":\\"4 cm\\",\\"nature\\":\\"beton_arme\\"},'
    '{\\"nom\\":\\"Entrevous béton\\",\\"epaisseur\\":\\"16 cm\\",\\"nature\\":\\"hourdis\\"}]", '
    '"type_poutrelle": "béton précontraint", "entraxe": "0,60 m"}}\n'
    "   IMPORTANT plancher_hourdis : inclure TOUTES les couches du haut vers le bas : "
    "revêtement de sol (carrelage/parquet) → chape → isolant → dalle de répartition "
    "→ entrevous/hourdis. Ne pas s'arrêter à la structure porteuse.\n"
    '   plancher_bois : {"schema_type": "plancher_bois", '
    '"title": "Plancher bois R+1", "params": {"couches": '
    '"[{\\"nom\\":\\"Panneaux OSB\\",\\"epaisseur\\":\\"2.2 cm\\",\\"nature\\":\\"bois\\"},'
    '{\\"nom\\":\\"Solivage bois\\",\\"epaisseur\\":\\"20 cm\\",\\"nature\\":\\"bois\\"},'
    '{\\"nom\\":\\"Faux-plafond OSB\\",\\"epaisseur\\":\\"1 cm\\",\\"nature\\":\\"bois\\"}]", '
    '"type_solivage": "sapin du nord traité", "section_solivage": "80×200 mm", '
    '"entraxe": "0,50 m"}}\n'
    "   IMPORTANT plancher_bois : le solivage a une SECTION (ex: 80×200 mm), "
    "pas une épaisseur de couche plate. Utiliser la HAUTEUR de la section comme "
    "epaisseur de la couche (ex: section 80×200 → epaisseur '20 cm'). "
    "Renseigner section_solivage avec la section complète (ex: '80×200 mm').\n"
    '   mur_doublage : {"schema_type": "mur_doublage", '
    '"title": "Mur avec doublage", "params": {"couches": '
    '"[{\\"nom\\":\\"Enduit\\",\\"epaisseur\\":\\"2 cm\\",\\"nature\\":\\"enduit\\"},'
    '{\\"nom\\":\\"Parpaing\\",\\"epaisseur\\":\\"20 cm\\",\\"nature\\":\\"beton\\"},'
    '{\\"nom\\":\\"Laine de verre\\",\\"epaisseur\\":\\"10 cm\\",\\"nature\\":\\"isolant_thermique\\"},'
    '{\\"nom\\":\\"Plaque de plâtre\\",\\"epaisseur\\":\\"1.3 cm\\",\\"nature\\":\\"plaque_platre\\"}]", '
    '"type_isolation": "ITI"}}\n'
    "   HIÉRARCHIE mur_doublage vs cloison :\n"
    "   - 'cloison de distribution', 'cloison intérieure', 'cloison 72/48', "
    "'cloison 98/48', 'cloison Placostil' → cloison "
    "(paroi intérieure sur ossature métallique, PAS de mur maçonné)\n"
    "   - 'mur extérieur', 'paroi extérieure', 'doublage', 'mur avec doublage' "
    "→ mur_doublage (mur maçonné + doublage isolant)\n"
    "   IMPORTANT cloison : l'isolant (laine minérale) est posé ENTRE les montants "
    "de l'ossature métallique, pas à côté. Combiner ossature + isolant en UNE SEULE "
    "couche avec nature 'ossature_isolant'. L'épaisseur = celle de l'ossature "
    "(ex: 4.8 cm pour ossature 48 mm). Le nom doit mentionner les deux composants "
    "(ex: 'Ossature 48mm + Laine minérale 45mm').\n"
    "   IMPORTANT cloison — UN SEUL TYPE PAR SCHÉMA : si le contexte contient "
    "plusieurs types de cloisons (ex: 72/48 ET 98/48), choisir UNIQUEMENT le type "
    "PRINCIPAL (celui avec le plus de surface ou le plus mentionné). "
    "NE JAMAIS fusionner plusieurs types dans un seul schéma. "
    "Le titre et type_cloison doivent correspondre à UN SEUL type.\n"
    '   cloison : {"schema_type": "cloison", '
    '"title": "Cloison de distribution 72/48", "params": {"couches": '
    '"[{\\"nom\\":\\"Plaque de plâtre BA13\\",\\"epaisseur\\":\\"1.3 cm\\",\\"nature\\":\\"plaque_platre\\"},'
    '{\\"nom\\":\\"Ossature 48mm + Laine minérale 45mm\\",\\"epaisseur\\":\\"4.8 cm\\",\\"nature\\":\\"ossature_isolant\\"},'
    '{\\"nom\\":\\"Plaque de plâtre BA13\\",\\"epaisseur\\":\\"1.3 cm\\",\\"nature\\":\\"plaque_platre\\"}]", '
    '"type_cloison": "72/48 — 1×BA13 par face, laine minérale 45 mm entre montants"}}\n'
    '   voirie : {"schema_type": "voirie", '
    '"title": "Structure de chaussée", "params": {"couches": '
    '"[{\\"nom\\":\\"Enrobé BB\\",\\"epaisseur\\":\\"6 cm\\",\\"nature\\":\\"enrobe\\"},'
    '{\\"nom\\":\\"Grave bitume\\",\\"epaisseur\\":\\"10 cm\\",\\"nature\\":\\"grave\\"},'
    '{\\"nom\\":\\"GNT\\",\\"epaisseur\\":\\"20 cm\\",\\"nature\\":\\"gravier\\"},'
    '{\\"nom\\":\\"Couche de forme\\",\\"epaisseur\\":\\"30 cm\\",\\"nature\\":\\"grave\\"}]", '
    '"classe_trafic": "T3"}}\n'
    "6. IMPORTANT — Pour coupe_geotechnique (sols/géotechnique) :\n"
    "   - couches : JSON array des couches de sol, du haut vers le bas.\n"
    '     Chaque couche = {"nom": "...", "epaisseur": "...", "nature": "..."}\n'
    "     nature parmi : vegetale, remblai, argile, limon, sable, gravier, marne, roche, calcaire\n"
    '     Pour la derniere couche (substratum), epaisseur = "inf"\n'
    "   - niveau_nappe : profondeur de la nappe (ex: '-2.50') ou null si non mentionnee\n"
    "   - profondeur_bon_sol : profondeur du bon sol (ex: '-2.50')\n"
    "   - portance : contrainte admissible (ex: '2.5 bars')\n"
    "   - nature_bon_sol : description courte du sol porteur\n"
    "   Exemple :\n"
    '   {"schema_type": "coupe_geotechnique", "title": "Coupe géotechnique — Sondage S1",\n'
    '    "params": {"couches": "[{\\"nom\\":\\"Terre végétale\\",\\"epaisseur\\":\\"0.30\\",\\"nature\\":\\"vegetale\\"},'
    '{\\"nom\\":\\"Argile brune\\",\\"epaisseur\\":\\"1.50\\",\\"nature\\":\\"argile\\"},'
    '{\\"nom\\":\\"Grave compacte\\",\\"epaisseur\\":\\"inf\\",\\"nature\\":\\"gravier\\"}]",\n'
    '    "niveau_nappe": "-2.50", "profondeur_bon_sol": "-1.80",\n'
    '    "portance": "2.5 bars", "nature_bon_sol": "Grave compacte"}}\n\n'
    "7. Si AUCUN schéma pertinent, AUCUNE dimension, ou si l'ouvrage ne correspond "
    'PAS exactement à un type ci-dessus, réponds : {"schema_type": "none"}\n'
    'Exemples de cas "none" : soubassement, mur enterré, blocs à bancher, '
    "fondation superficielle (hors semelle), drainage, enduit imperméabilisation.\n"
    "8. Génère un titre court et descriptif.\n"
    "9. Réponds UNIQUEMENT au format JSON :\n"
    '{"schema_type": "semelle_filante", "title": "Semelle filante", '
    '"params": {"B": "50 cm", "H": "20 cm", '
    '"fond_fouille": "-1,33 m / TN", "bon_sol": "grave naturelle"}}\n'
    "ou\n"
    '{"schema_type": "none"}'
)

# ── Query rewrite prompt ─────────────────────────────────────────

REWRITE_PROMPT = (
    "Tu es un assistant de recherche documentaire pour le BTP. "
    "À partir de la question de l'utilisateur et de l'historique de conversation, "
    "génère une requête de recherche optimisée pour trouver les passages pertinents "
    "dans des documents techniques (CCTP, bilan thermique, DPGF, etc.).\n\n"
    "Règles :\n"
    "1. Si la question n'a AUCUN rapport avec le BTP, la construction, "
    "l'architecture ou les documents techniques, réponds exactement : HORS_SUJET\n"
    "2. Les questions générales sur le projet (résumé, acteurs, client, budget, "
    "planning, lots, type de construction) sont TOUJOURS liées au BTP — ne les "
    "marque JAMAIS comme HORS_SUJET. Reformule-les en termes de recherche "
    "(ex: 'résume le projet' → 'maître ouvrage type construction lots description projet objet travaux').\n"
    "3. CONCISION OBLIGATOIRE : la requête reformulée doit faire 5 à 20 mots MAX. "
    "Utilise les termes techniques du domaine BTP (matériaux, ouvrages, dimensions) "
    "mais JAMAIS de références normatives (NF, DTU, articles de loi, codes), "
    "JAMAIS de méthodes d'analyse (laboratoire, microscopie, prélèvements), "
    "JAMAIS d'acronymes réglementaires (VLEP, COFRAC, DAAT, SS3, SS4). "
    "La requête doit ressembler à ce qu'un économiste chercherait, pas à un mémoire. "
    "Ex: 'parois intérieures' → 'isolation murs résistance thermique épaisseur isolant doublage' ; "
    "'comment est l'amiante' → 'amiante repérage matériaux localisation état conservation'.\n"
    "4. Résous les références implicites grâce à l'historique "
    "(ex: 'et pour les murs ?' après une question sur l'isolation → "
    "'isolation thermique murs résistance R épaisseur isolant').\n"
    "5. Détermine si un tableau comparatif CCTP/DPGF serait pertinent :\n"
    '   - "table" : ouvrage technique précis '
    "avec caractéristiques chiffrées (dimensions, matériaux, prix, quantités)\n"
    '   - "none" : question générale, descriptive, énumération ou hors sujet\n'
    "6. Détermine si un schéma technique en coupe serait pertinent :\n"
    '   - "schema" : ouvrage dont on peut dessiner une coupe '
    "(fondation, dallage, mur, plancher, toiture, voirie, charpente, sol). "
    "Inclut les questions sur la COMPOSITION d'un ouvrage "
    "('comment est le plancher', 'composition du mur')\n"
    '   - "none" : pas de schéma pertinent\n'
    "7. Pour les questions sur un ouvrage technique précis, "
    "génère 1 à 2 requêtes complémentaires COURTES (5-15 mots) dans le champ 'related'. "
    "Ces requêtes doivent cibler les concepts constructifs ADJACENTS dans le processus "
    "de construction, pas des reformulations ni des synonymes. "
    "Exemples : semelles → 'fond de fouille terrassement profondeur bon sol' ; "
    "isolation murs → 'doublage plaque de plâtre enduit parement'. "
    "Pour les questions diagnostiques (amiante, sol, thermique), 'related' = [] (liste vide).\n"
    "8. Réponds UNIQUEMENT au format JSON (sans markdown) :\n"
    '   {"query": "requête reformulée", "related": ["...", "..."], "structured": "table|none", "schema": "schema|none"}'
)

# ── System prompt (RAG answer) ───────────────────────────────────

SYSTEM_PROMPT = (
    "Tu es un assistant expert en économie de la construction et en BTP. "
    "Tu réponds en français, de manière précise et professionnelle.\n\n"
    "RÈGLES :\n"
    "1. Base-toi UNIQUEMENT sur les documents fournis dans le contexte.\n"
    "2. Ne cite JAMAIS de source dans le corps de ta réponse. "
    "Pas de [fichier, p.X], pas de crochets, pas de références. "
    "Les sources sont gérées automatiquement et affichées séparément.\n"
    "3. Ne fabrique JAMAIS d'information. Si tu as des éléments partiels, "
    "réponds avec ce que tu as. Si rien ne correspond, dis-le en une phrase. "
    "INTERDIT de signaler qu'une info est absente, manquante, non précisée, "
    "non mentionnée ou incomplète — ni en toutes lettres, ni via des formulations "
    "détournées ('à confirmer', 'non détaillé', etc.). "
    "Si tu n'as pas la valeur, n'en parle pas.\n"
    "4. Sois CONCIS : va droit au fait, pas de paraphrase ni de formules de politesse.\n"
    "5. DONNÉES TECHNIQUES : inclus TOUJOURS les dimensions COMPLÈTES "
    "(longueur × largeur × épaisseur, format, section) et références "
    "quand elles sont dans le contexte. Ne résume jamais à une seule dimension "
    "si la section complète est disponible. "
    "Dimensions BRUTES : '50×20 cm' et NON '50×20 cm (largeur × hauteur)'.\n"
    "6. Réponds en 2 à 6 phrases par point. Question simple = une phrase.\n"
    "7. LOTS : liste UNIQUEMENT les lots explicitement identifiés 'LOT n°...' "
    "dans les documents. Ne déduis pas de lots depuis des thématiques. "
    "Recopie les intitulés EXACTEMENT.\n"
    "8. PERTINENCE : inclus UNIQUEMENT les ouvrages répondant DIRECTEMENT à la question. "
    "Ne mélange pas les corps d'état. Revêtement de sol = finition visible "
    "(carrelage, parquet, moquette, résine), pas les sous-couches ni chapes.\n"
    "9. CONVENTION 'HAUT' : 'haut RDC' = plancher du R+1, "
    "'haut R+1' = plancher du R+2, 'haut sous-sol' = plancher du RDC.\n\n"
    "FORMATAGE :\n"
    "10. Utilise le Markdown avec **gras** pour les termes techniques importants.\n"
    "11. STRUCTURE OBLIGATOIRE pour décrire un ouvrage — UN SEUL BLOC par ouvrage :\n"
    "   a) UNE phrase d'introduction résumant l'ouvrage (ex: 'Les fondations reposent "
    "sur des **semelles filantes en béton armé C25/30**, coulées en pleine fouille "
    "sur béton de propreté. L'ensemble comprend :')\n"
    "   b) Liste à puces (- **Élément** : description) — un composant par ligne. "
    "TOUS les composants de l'ouvrage dans la MÊME liste, même s'ils proviennent "
    "de lots différents (gros-œuvre, isolation, enduit, doublage).\n"
    "   c) LOCALISATION :\n"
    "   Le mot 'Localisation' NE DOIT APPARAÎTRE QU’UNE SEULE FOIS dans toute la réponse.\n"
    "   Il doit être placé UNIQUEMENT à la toute fin.\n"
    "\n"
    "   Si 'Localisation' apparaît ailleurs → la réponse est FAUSSE et doit être corrigée.\n"
    "\n"
    "   INTERDIT :\n"
    "   - Localisation après une variante\n"
    "   - Localisation au milieu\n"
    "   - plusieurs blocs Localisation\n"
    "\n"
    "   FORMAT FINAL UNIQUE :\n"
    "   **Localisation :** liste récapitulative de toutes les variantes.\n"
    "   d) UN SEUL bloc **Normes** tout à la fin, APRÈS le bloc Localisation, "
    "regroupant tous les DTU/NF EN applicables.\n"
    "   ORDRE STRICT en fin de réponse : **Localisation** puis **Normes** — rien après.\n"
    "   Si plusieurs variantes d'un même ouvrage (ex: couverture 45° et 35°, "
    "cloison 72/48 et 98/48), les décrire toutes PUIS un seul bloc Localisation "
    "récapitulatif, pas un bloc Localisation par variante.\n"
    "   INTERDIT de créer plusieurs blocs séparés pour le même ouvrage. "
    "Ex: paroi extérieure = UN bloc avec maçonnerie + enduit + doublage + isolation, "
    "pas un bloc 'maçonnerie' puis un bloc 'enduit' chacun avec sa localisation/normes.\n"
    "12. Sépare les paragraphes par une ligne vide. "
    "Pas de titres (#), de tableaux, ni de blocs de code."
    "13. VALIDATION FINALE (OBLIGATOIRE) :\n"
    "Avant d’envoyer la réponse :\n"
    "- Compter le nombre de 'Localisation'\n"
    "- Si ≠ 1 → corriger\n"
    "- Vérifier qu’il est à la fin → sinon corriger\n"
)

LOCALISATION_INSTRUCTION = (
    "\n\nLOCALISATION — RÈGLE STRICTE :\n"
    "INTERDIT d'écrire 'Localisation :' après chaque élément ou variante. "
    "APRÈS avoir décrit TOUS les éléments et TOUTES les variantes, "
    "ajoute UN SEUL bloc récapitulatif TOUT À LA FIN (avant Normes) :\n"
    "**Localisation :**\n"
    "- Élément/variante A : lieu A.\n"
    "- Élément/variante B : lieu B.\n"
    "UNIQUEMENT le lieu (pièce, façade, étage, zone). "
    "PAS de cotes altimétriques, niveaux de plateforme, dimensions, ou détails techniques "
    "dans le bloc localisation — ces infos sont déjà dans la description de l'ouvrage.\n"
    "Si aucune localisation PRÉCISE n'est dans le contexte, ne mets pas ce bloc. "
    "INTERDIT d'écrire des localisations évidentes ou génériques "
    "('ensemble du bâtiment', 'tout le projet', 'toute la construction')."
)

# ── Ouvrage enrichment instructions (injected dynamically) ──────

OUVRAGE_INSTRUCTIONS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"paroi.?ext[ée]rieur|mur.?ext[ée]rieur|mur.?p[ée]riph[ée]rique",
            re.IGNORECASE,
        ),
        "\n\nCOMPOSITION DES PAROIS EXTÉRIEURES — RÈGLE :\n"
        "Décris TOUJOURS la composition complète EN UN SEUL BLOC, de l'extérieur vers l'intérieur :\n"
        "enduit extérieur → maçonnerie (agglo, brique, béton) → isolation "
        "(laine de verre, PSE, polyuréthane) → parement intérieur (plaque de plâtre, BA13).\n"
        "Ces éléments viennent souvent de lots différents (Gros-œuvre, Cloisons sèches, Enduit) "
        "— cherche dans TOUT le contexte, pas seulement dans un seul lot.\n"
        "STRUCTURE ATTENDUE :\n"
        "1. Phrase d'introduction décrivant la paroi globale\n"
        "2. **Parois** : maçonnerie (agglo, brique, béton) avec ses composants (raidisseurs, chaînages)\n"
        "3. **Doublage** : isolation + parement intérieur (plaque de plâtre, BA13)\n"
        "4. **Enduit extérieur** : type d'enduit, finition, seuils\n"
        "5. UN SEUL bloc Localisation à la fin\n"
        "6. UN SEUL bloc Normes à la fin (tous les DTU : 20.1, 26.1, 25.41, etc.)\n",
    ),
]


def get_ouvrage_instruction(question: str) -> str:
    """Return dynamic instruction if the question matches an ouvrage pattern."""
    for pattern, instruction in OUVRAGE_INSTRUCTIONS:
        if pattern.search(question):
            return instruction
    return ""


# ── Table extraction prompt ──────────────────────────────────────

TABLE_EXTRACTION_PROMPT = (
    "Tu es un expert en économie de la construction. "
    "À partir du contexte documentaire, synthétise les données techniques "
    "sous forme de tableau JSON.\n\n"
    "Format JSON strict (TOUJOURS 4 colonnes) :\n"
    "{\n"
    '  "title": "Titre court (ex: Semelles de fondation)",\n'
    '  "columns": ["Élément", "Description", "Quantité", "Localisation"],\n'
    '  "rows": [{"element": "...", "description": "...", "quantite": "...", "localisation": "..."}]\n'
    "}\n\n"
    "IMPORTANT — Description : CONCISE (max ~15 mots). "
    "Inclure : matériau, dimensions clés, marque/référence si disponible. "
    "EXCLURE : lignes de calcul (ex: 2f12,30+11,28+2f6,26), "
    "formules, détails de dosage, parenthèses explicatives d'axes "
    "(écrire '0,50×0,20 m' et NON '0,50×0,20 m (largeur × hauteur)'). "
    "Ex: 'Béton armé section 0,50×0,20 m', 'Gros béton ép. 5 cm', "
    "Ne jamais résumer à une seule dimension si la section complète est disponible.\n\n"
    "IMPORTANT — Quantité : unité dans la valeur (m³, m², ml, kg, U, etc). "
    "Cherche dans les sous-articles DPGF et extrais le TOTAL chiffré. "
    "CHAQUE ligne DOIT avoir une valeur chiffrée — SUPPRIME les lignes sans quantité. "
    'Si AUCUN ouvrage n\'a de quantité chiffrée, réponds : {"skip": true}\n\n'
    "IMPORTANT — Localisation : lieu mentionné dans le contexte "
    "(ex: 'maison principale', 'garage', 'RDC', 'étage'). "
    "Si aucune localisation n'est mentionnée pour une ligne, écrire '—'.\n\n"
    "IMPORTANT — Convention 'haut' dans les CCTP/DPGF : "
    "'haut RDC' = plancher du R+1, 'haut R+1' = plancher du R+2, "
    "'haut sous-sol' = plancher du RDC. "
    "Donc 'solivage haut RDC du garage' se localise au R+1, PAS au RDC. "
    "Si la question porte sur le plancher du RDC, exclure les éléments 'haut RDC' "
    "(qui appartiennent au R+1).\n\n"
    "Règles :\n"
    "1. 3 à 8 lignes MAX. Que les données essentielles et concrètes.\n"
    "2. UNIQUEMENT ce qui est explicitement dans le contexte. Ne rien inventer.\n"
    "3. Valeurs courtes et précises (ex: 'Béton C25/30', '50 cm', '4.84 m³', '35 €/ml').\n"
    "4. UNE SEULE LIGNE par type d'ouvrage. Si le même ouvrage apparaît à "
    "plusieurs localisations avec des quantités différentes, FUSIONNE en une ligne : "
    "additionne les quantités et liste les localisations. "
    "Ex: Enduit qui apparaît 26.66 m² + 6.02 m² → une seule ligne '32.68 m²' avec "
    "'parois enterrées (dont façade Est)'. "
    "NE JAMAIS avoir 2 lignes avec le même élément.\n"
    "5. PERTINENCE : inclus UNIQUEMENT les ouvrages qui répondent DIRECTEMENT "
    "à la question posée. Exemples :\n"
    "   - Fondations → semelles, béton de propreté, fouilles en rigole. "
    "PAS de mise à la terre (lot Électricité), maçonnerie de soubassement, "
    "chaînages, drainage, enduits d'imperméabilisation.\n"
    "   - Revêtements de sol → PAS de plinthes, faïence, chape d'arase, isolation, étanchéité. "
    "Un revêtement = finition visible (carrelage, parquet, moquette, résine).\n"
    "   - Plancher RDC → PAS de linteaux, chaînages verticaux, maçonnerie de murs, "
    "menuiseries, enduits. Un plancher = structure porteuse horizontale "
    "(poutrelles, entrevous, dalle, hourdis, solivage) + ses composants directs "
    "(chape, isolation sous dalle, réservations dans le plancher).\n"
    "6. JSON uniquement, rien d'autre."
)

# ── Keyword patterns ─────────────────────────────────────────────

OFF_TOPIC = "HORS_SUJET"

FORCED_RELATED: list[tuple[re.Pattern[str], list[str]]] = [
    (
        re.compile(
            r"soubassement|mur.?enterr[ée]|infrastructure|vide.?sanitaire|paroi.?enterr[ée]",
            re.IGNORECASE,
        ),
        [
            "agglomérés pleins blocs à bancher voile béton soubassement élévation",
            "longrine maçonnerie soubassement mur enterré paroi",
            "enduit imperméabilisation étanchéité drainage parois enterrées",
            "vide sanitaire plancher hourdis sur longrines",
        ],
    ),
    (
        re.compile(
            r"mur(?!.*(?:enterr|soubassement))|paroi.?ext[ée]rieur|fa[çc]ade", re.IGNORECASE
        ),
        [
            "enduit extérieur façade monocouche RPE crépi ravalement mortier bâtard",
            "maçonnerie agglo parpaing brique béton banché ossature bois mur porteur",
            "isolation thermique doublage laine de verre laine de roche polyuréthane ITE ITI",
            "plaque de plâtre BA13 parement intérieur finition",
        ],
    ),
]

FORCED_SCHEMA_RE = re.compile(
    r"dallage|terre.plein|plancher|hourdis|solivage|plancher.bois"
    r"|toiture.terrasse|mur.*doublage|cloison"
    r"|charpente|couverture|voirie|chauss[ée]e|composition.*mur"
    r"|composition.*plancher|composition.*dallage|coupe.*mur"
    r"|coupe.*plancher|coupe.*toiture|coupe.*dallage",
    re.IGNORECASE,
)


def get_forced_related(query: str) -> list[str]:
    """Return deterministic related queries based on keyword detection."""
    extras: list[str] = []
    for pattern, queries in FORCED_RELATED:
        if pattern.search(query):
            extras.extend(queries)
    return extras


# ── Score boost for forced related queries ───────────────────────

FORCED_SCORE_FLOOR = 0.45

# ── Deterministic scope classification ───────────────────────────

_BROAD_SCOPE_RE = re.compile(
    r"quell?e?s?\s+sont|liste[rz]?\b|r[ée]sum[ée]|synth[èe]se|vue\s+d.ensemble"
    r"|tous\s+les|budget|ma[iî]tre\s+d.ouvrage|type\s+de\s+construction"
    r"|combien\s+de|c.est\s+quoi\s+ce\s+projet"
    r"|contraintes?\s+(?:du|de|r[ée]glementaire|projet|chantier)"
    r"|normes?\s+applicables?|dtu\s+applicables?",
    re.IGNORECASE,
)


def classify_scope(question: str) -> str:
    """Classify question scope deterministically: 'broad' or 'specific'."""
    if _BROAD_SCOPE_RE.search(question):
        return "broad"
    return "specific"
