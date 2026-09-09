"""Summary service — multi-pass RAG generation of structured project summaries."""

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime

from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mistral import mistral_client
from app.core.qdrant import qdrant_client
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.project import Project
from app.models.summary import ProjectSummary
from app.schemas.summary import (
    ContrainteItem,
    ProjectSummaryData,
    SummarySchemaData,
    SummaryStatusRead,
    SystemeConstructifItem,
)
from app.services.ingestion.classification import TYPE_CCTP, TYPE_DPGF
from app.services.ingestion.embedding import COLLECTION_NAME, embed_texts

logger = logging.getLogger(__name__)

LLM_MODEL = "mistral-large-latest"
CONCURRENCY_LIMIT = 4

_SMALL_THRESHOLD = 500
_LARGE_THRESHOLD = 5000


def _get_search_params(chunk_count: int) -> tuple[int, int]:
    """Return (search_limit_per_query, max_context_chars) based on project size."""
    if chunk_count < _SMALL_THRESHOLD:
        return 10, 30_000
    if chunk_count < _LARGE_THRESHOLD:
        return 15, 45_000
    return 20, 60_000


@dataclass
class SectionConfig:
    key: str
    label: str
    search_queries: list[str]
    schema_type: str | None
    prompt: str
    category: str
    doc_types: list[str] = field(default_factory=list)
    exclude_content_types: list[str] = field(default_factory=list)


SECTION_CONFIGS: list[SectionConfig] = [
    # ── Building system ──
    SectionConfig(
        key="sol",
        label="Terrain et sol",
        search_queries=[
            "rapport de sol géotechnique portance terrain naturel",
            "TN moyen bon sol cote fouilles terrassement pleine masse",
            "étude de sol G2 sondages préssiomètre",
        ],
        schema_type=None,
        prompt=(
            "Extrais les informations ESSENTIELLES sur le sol du projet :\n"
            "- Nature du terrain (toute nature, roche, argiles, remblais...)\n"
            "- Portance, contrainte admissible si connue\n"
            "- Cotes principales : TN, fond de fouille, plate-forme, sol fini\n"
            "- Risques : nappe, retrait-gonflement, remblais\n\n"
            "IMPORTANT — Format des details :\n"
            "- TOUJOURS regrouper les valeurs d'un même type sur UNE SEULE ligne.\n"
            "  Exemple correct : 'TN : +0,15m (maison) / +0,05m (garage)'\n"
            "  Exemple incorrect : 'TN maison +0,15m' puis 'TN garage +0,05m'\n"
            "- Garder UNIQUEMENT les cotes principales (TN, fond de fouille, plate-forme, sol fini). "
            "Maximum 5-6 details au total.\n"
            "- Ne PAS inclure les détails opérationnels de terrassement "
            "(pente des talus, blindage, fossés, drainage, tri des déblais, "
            "mise en dépôt, protection). Ce sont des prescriptions de chantier, pas un résumé.\n"
            "- Ne PAS inclure de volumes, quantités ni métrés (m3, m2, ml)\n"
            "- Ne PAS inclure les fondations (semelles, longrines) ni le dallage ici."
        ),
        category="constructif",
    ),
    SectionConfig(
        key="infrastructure",
        label="Infrastructure",
        search_queries=[
            "fondations semelles filantes isolées longrines béton armé",
            "murs de soubassement agglo béton vide sanitaire hauteur épaisseur 20",
            "plancher bas hourdis poutrelles terre-plein dallage dalle radier",
            "protection humidité arases étanches chape bitumineuse",
            "enduit imperméabilisation parois enterrées",
            "drainage périphérique fondations graviers géotextile",
        ],
        schema_type="semelle_filante",
        prompt=(
            "Extrais les informations sur l'infrastructure du bâtiment principal.\n"
            "Les 4 éléments à extraire (chacun doit être un detail séparé) :\n"
            "1. Fondations : type et dimensions (ex: 'Semelles filantes 50×20 cm', 'Micropieux Ø250 mm')\n"
            "2. Soubassement : matériau EXACT (plein ou creux) + épaisseur. "
            "L'épaisseur peut se trouver dans le CCTP (sous-article type 'En 20 creux') "
            "ou dans le DPGF (ligne de métré). "
            "Ex: 'Soubassement en agglomérés pleins 20 cm' ou "
            "'Soubassement en agglomérés creux 20 cm'.\n"
            "3. Plancher bas : type + épaisseur. "
            "Ex: 'Plancher semi-préfabriqué type 16+4', 'Dallage sur terre-plein ep. 13 cm'. "
            "Le '+4' représente DÉJÀ la dalle de répartition — ne PAS ajouter "
            "un detail séparé 'Dalle de répartition'. "
            "C'est un élément ESSENTIEL, il DOIT apparaître dans les details.\n"
            "4. Protection contre l'humidité (si mentionnée) : résumer en UN SEUL detail "
            "l'ENSEMBLE du système d'étanchéité décrit dans le contexte. "
            "Le système peut comporter PLUSIEURS composants distincts "
            "(par ex. arases étanches, enduit d'imperméabilisation, drainage). "
            "Tu DOIS parcourir TOUS les passages du contexte relatifs à la protection "
            "contre l'humidité et les combiner dans une seule phrase. "
            "Ne t'arrête PAS au premier composant trouvé — "
            "continue à chercher dans le reste du contexte.\n"
            "Ne PAS inclure la chape d'arase étanche (feutre bitumeux sur mortier hydrofugé) — "
            "c'est un détail de mise en œuvre du soubassement, pas un composant du système d'étanchéité. "
            "Garder uniquement : protection des arases (type + produit), "
            "enduit d'imperméabilisation (type + produit), drainage périphérique (composition).\n\n"
            "IMPORTANT :\n"
            "- Se concentrer sur le bâtiment principal, pas les annexes secondaires "
            "(garage, local technique, abri, batiment B). Si une annexe a un soubassement "
            "différent, ne pas le mentionner.\n"
            "- Toujours donner l'ÉPAISSEUR et les DIMENSIONS indiquées dans le CCTP. "
            "Si le CCTP donne une épaisseur ou une section, la reprendre telle quelle. "
            "Si la dimension n'est pas donnée dans le CCTP, écrire juste le type "
            "SANS ajouter de commentaire. Ex: 'Semelles filantes en béton armé' "
            "(et NON 'Semelles en béton armé (dimensions non précisées)').\n"
            "- Ne JAMAIS écrire 'à confirmer', 'à valider par BET', 'selon étude', "
            "'non précisé', 'non spécifié', 'épaisseur à valider'. "
            "Ces mentions polluent le résumé.\n"
            "- Ne PAS inclure les éléments secondaires : béton de propreté/gros béton, "
            "film polyane, relevé de plinthe, planelles, radiers locaux (PAC, local technique), "
            "trappes d'accès, regards, ventilation de vide sanitaire, grilles moustiquaires, "
            "cours anglaises, état de surface, dalle de répartition. "
            "Ces éléments n'ont pas leur place dans un résumé.\n"
            "- Ne PAS dédoubler les articles : un seul detail par élément "
            "(ex: un seul detail pour le soubassement, pas deux variantes).\n"
            "- Ne PAS lister les surfaces, volumes, métrés.\n"
            "- Maximum 4 details (fondations, soubassement, plancher bas, protection humidité).\n\n"
        ),
        category="constructif",
        doc_types=[TYPE_CCTP, TYPE_DPGF],
        exclude_content_types=["quantity"],
    ),
    SectionConfig(
        key="elevation",
        label="Élévation",
        search_queries=[
            "murs porteurs agglo béton doublage isolation",
            "maçonnerie agglomérés ciment creux épaisseur 20 mur élévation",
            "isolation thermique intérieure ITI laine enduit façade",
            "plancher intermédiaire étage dalle solivage hourdis prédalles",
        ],
        schema_type="mur_doublage",
        prompt=(
            "Extrais les informations sur l'élévation du projet.\n"
            "Les éléments OBLIGATOIRES à extraire dans cet ORDRE (extérieur → intérieur) :\n"
            "1. Enduit extérieur : type (ex: 'Enduit monocouche' ou 'Enduit au mortier bâtard')\n"
            "2. Mur porteur : matériau + épaisseur, sans prescription de pose. "
            "Ex: 'Agglomérés de ciment creux 20 cm' "
            "(et NON 'Agglomérés de ciment creux hourdés au mortier de ciment' — "
            "'hourdés au mortier' est un mode de mise en œuvre, pas un résumé).\n"
            "3. Doublage intérieur : préciser ITI ou ITE dans le detail, "
            "puis décrire comme UN SEUL système avec épaisseur totale, isolant et parement. "
            "Ex: 'Doublage ITI Placostil ep. 160 mm, laine de verre GR32 120 mm + BA13' "
            "ou 'ITE PSE ep. 160 mm + enduit mince'. "
            "Ne JAMAIS séparer l'isolant et la plaque de plâtre en details distincts — "
            "c'est UN seul ouvrage. Ne PAS faire un detail séparé 'ITI' ou 'ITE', "
            "c'est intégré dans le detail du doublage.\n"
            "4. Planchers d'étage (Haut RDC, Plancher haut, R+1 et au-delà) : type + épaisseur. "
            "C'est un élément ESSENTIEL s'il y a un étage, il DOIT apparaître "
            "dans les details. Isolation acoustique si mentionnée.\n\n"
            "IMPORTANT :\n"
            "- ORDRE des details : extérieur → intérieur, plancher d'étage en dernier.\n"
            "- Toujours inclure l'ÉPAISSEUR du mur porteur. "
            "Si le CCTP ne la donne pas, omettre sans écrire 'non précisé'.\n"
            "- Ne PAS inclure les prescriptions de pose / mise en œuvre : "
            "'hourdés au mortier de ciment', fourrures métalliques, cavaliers, "
            "tiges filetées, chevillage, entraxe, protection pied de cloison.\n"
            "- Ne PAS inclure les traitements spécifiques à une façade "
            "(enduit d'imperméabilisation localisé, traitement anti-humidité).\n"
            "- Ne PAS inclure le plancher bas (traité en Infrastructure).\n"
            "- Ne PAS inclure le plancher du comble non habitable.\n"
            "- Ne PAS inclure de volumes, quantités ni métrés.\n"
            "- Maximum 4-5 details pertinents.\n\n"
            "Pour le schéma, extrais les couches [{nom, epaisseur, nature}] et type_isolation."
        ),
        category="constructif",
        doc_types=[TYPE_CCTP],
        exclude_content_types=["quantity"],
    ),
    SectionConfig(
        key="revetement_sol",
        label="Revêtement de sol",
        search_queries=[
            "isolation sol polyuréthane polystyrène chape revêtement",
            "carrelage parquet revêtement sol RDC étage",
            "chape mortier ciment chape fluide chape traditionnelle épaisseur",
            "plancher chauffant chape fluide chape traditionnelle",
        ],
        schema_type=None,
        prompt=(
            "Extrais les informations sur le revêtement de sol du projet.\n"
            "Pour la description, résumer PRÉCISÉMENT quel type de finition est utilisé "
            "à quel endroit — ne pas généraliser si les finitions diffèrent selon les niveaux ou pièces. "
            "Dans la description, utiliser uniquement les termes GÉNÉRIQUES (carrelage grès cérame, "
            "parquet stratifié, etc.) SANS marques ni noms commerciaux. "
            "Les marques et références sont réservées aux details.\n"
            "Créer UN detail par type de sol distinct. Si un niveau a des sols différents "
            "selon les pièces (ex: carrelage en pièces humides, parquet ailleurs), "
            "créer un detail séparé pour chaque.\n\n"
            "FORMAT de chaque detail — commencer par 'Sol du/de la [localisation] comprenant' "
            "puis la composition complète (de bas en haut, séparée par des +) :\n"
            "Ex: 'Sol du RDC comprenant isolation [type] [épaisseur] (R=[valeur]) + chape au mortier de ciment [épaisseur] + [finition] [dimensions]'\n"
            "Ex: 'Sol de la SdB du R+1 comprenant [support] [épaisseur] + étanchéité par [système] + [finition]'\n"
            "Ex: 'Sol du R+1 comprenant sous-couche [type/référence] + [finition/référence]'\n\n"
            "IMPORTANT :\n"
            "- Toujours inclure le TYPE d'isolation (polyuréthane, polystyrène, laine...), "
            "son ÉPAISSEUR et sa RÉSISTANCE THERMIQUE R (ex: R = 4.65 m²K/W) si disponibles.\n"
            "- Toujours inclure l'ÉPAISSEUR de CHAQUE couche mentionnée dans le CCTP "
            "(support, chape, panneau OSB, etc.).\n"
            "- Pour la chape, toujours préciser son TYPE (mortier de ciment, fluide, anhydrite...) "
            "tel que décrit dans le CCTP.\n"
            "- Toujours inclure le TYPE de finition (carrelage, parquet, PVC...) "
            "avec les dimensions ou références EXACTES du document.\n"
            "- Inclure le NOM COMMERCIAL du produit si mentionné dans le CCTP "
            "(ex: TMS de EFYOS, BALANCE CLICK de QUICK-STEP), "
            "mais Ne PAS inclure les codes référence (ex: Ref : 6492692, BACL 40052).\n"
            "- Si plancher chauffant, le mentionner AVANT l'isolation.\n"
            "- Ne PAS inclure les éléments secondaires : film polyane, "
            "relevé de plinthe, joints, seuils, plinthes.\n"
            "- Ne PAS lister les surfaces, volumes, métrés.\n"
            "- Maximum 4 details.\n"
        ),
        category="constructif",
        doc_types=[TYPE_CCTP],
        exclude_content_types=["quantity"],
    ),
    SectionConfig(
        key="charpente",
        label="Charpente & Couverture",
        search_queries=[
            "charpente fermettes couverture tuiles",
            "isolation combles laine soufflée",
            "écran sous-toiture ventilation",
        ],
        schema_type="charpente_couverture",
        prompt=(
            "Extrais les informations sur la charpente et couverture.\n"
            "Les éléments à extraire (UN detail par élément, maximum 4 details, "
            "ou 5 si une étanchéité de toiture est mentionnée) :\n"
            "1. Charpente : type (fermettes, traditionnelle, non assemblée) + essence de bois. "
            "UNE SEULE ligne, pas de détails de quincaillerie "
            "(coupes, calages, ferrures, boulons, échantignoles, équerres).\n"
            "2. Couverture : matériau (tuiles, ardoises) + norme/classement si mentionné + garantie.\n"
            "3. Écran sous-toiture : type + référence produit si mentionnée.\n"
            "4. Isolation : type + épaisseur + R si disponible.\n"
            "5. Étanchéité de toiture (si mentionnée) : type de membrane ou système d'étanchéité.\n\n"
            "Ne PAS inclure :\n"
            "- Le mode de pose de la couverture (crochets, voliges, clous)\n"
            "- Le vide d'air entre volige et isolation\n"
            "- Les chatières et ventilation de toiture\n"
            "- Les noues, rives, faîtages, zinguerie\n"
            "- Les surfaces, volumes, métrés\n\n"
            "Pour le schéma, extrais les couches [{nom, epaisseur, nature}] et type_couverture."
        ),
        category="constructif",
        doc_types=[TYPE_CCTP],
        exclude_content_types=["quantity"],
    ),
    SectionConfig(
        key="menuiseries",
        label="Menuiseries extérieures",
        search_queries=[
            "menuiseries PVC aluminium double vitrage",
            "fenêtres baies vitrées volets roulants",
        ],
        schema_type=None,
        prompt=(
            "Extrais les informations sur les menuiseries extérieures.\n"
            "Les éléments à extraire (UN detail par élément, maximum 4 details) :\n"
            "1. Menuiseries : matériau(x) (PVC, aluminium, bois, mixte) + rupture de pont thermique si mentionné\n"
            "2. Vitrage : type (simple, double, triple, feuilleté) + composition si mentionnée + "
            "performances thermiques (Uw, Sw) SI mentionnées\n"
            "3. Volets : type (battants, roulants) + matériau + motorisation SI mentionnés\n"
            "4. Porte d'entrée SI mentionnée\n\n"
            "Ne PAS inclure :\n"
            "- Quincaillerie (béquillage, serrures, crémones, poignées)\n"
            "- Seuils, bavettes, appuis de fenêtre\n"
            "- Joints d'étanchéité (EPDM, compriband)\n"
            "- Cadres dormants, vantaux (ce sont des composants évidents)\n"
            "- Couleurs / finitions (RAL)\n\n"
            "IMPORTANT : extrais ce qui EST présent dans les documents. "
            "Si un coefficient thermique n'est pas précisé, ne l'inclus pas."
        ),
        category="constructif",
        doc_types=[TYPE_CCTP],
        exclude_content_types=["quantity"],
    ),
    SectionConfig(
        key="chauffage",
        label="Chauffage & ECS",
        search_queries=[
            "pompe à chaleur PAC chauffage plancher chauffant",
            "eau chaude sanitaire ballon thermodynamique VMC",
        ],
        schema_type=None,
        prompt=(
            "Extrais les informations sur le chauffage, l'ECS et la VMC.\n"
            "Les éléments à extraire (UN detail par élément, maximum 4 details) :\n"
            "1. Chauffage : type (PAC air/air, air/eau, gaz, électrique) + marque/modèle + "
            "émetteurs (ventilo-convecteurs, plancher chauffant, radiateurs)\n"
            "2. ECS : type (ballon thermodynamique, chauffe-eau, etc.) + capacité + marque/modèle\n"
            "3. VMC : type COMPLET (simple flux hygroréglable type A ou B, double flux, etc.) "
            "— le type (A ou B) est ESSENTIEL, ne pas l'omettre\n"
            "4. Régulation / programmation SI mentionnée\n\n"
            "Ne PAS inclure :\n"
            "- Prises d'air, bouches d'extraction, entrées d'air\n"
            "- Chapeau de ventilation, extraction en toiture\n"
            "- Détails de raccordement ou mise en œuvre\n"
            "- Surfaces, volumes, métrés"
        ),
        category="constructif",
        doc_types=[TYPE_CCTP],
        exclude_content_types=["quantity"],
    ),
    # ── Constraints (4) ──
    SectionConfig(
        key="thermique",
        label="Réglementation thermique",
        search_queries=[
            "RE 2020 zone climatique Bbio Cep",
            "bilan thermique étude thermique réglementaire",
            "Bbio max Cep max Ic énergie DH confort été",
            "synthèse étude thermique attestation RT RE",
        ],
        schema_type=None,
        prompt=(
            "Extrais les données de réglementation thermique.\n"
            "Les éléments à extraire :\n"
            "- Réglementation applicable (RT 2012, RE 2020)\n"
            "- Zone climatique\n"
            "- Altitude\n"
            "- Bbio projet et Bbio max\n"
            "- Cep projet et Cep max\n"
            "- Cep,nr projet et Cep,nr max (RE 2020)\n"
            "- Ic énergie et Ic construction (RE 2020)\n"
            "- Confort d'été : DH (degrés-heures) projet et seuil\n"
            "- Perméabilité à l'air Q4\n"
            "- Maximum 9 details.\n"
            "- UNIQUEMENT les éléments listés ci-dessus. Ne PAS ajouter d'autres types "
            "d'informations même si elles sont présentes dans les documents.\n"
            "\n"
            "Ne PAS inclure :\n"
            "- Les modalités de test (test intermédiaire, test final, PV, bureau agréé)\n"
            "- Les prescriptions de mise en œuvre\n"
            "- Les surfaces (SHAB, SHONRT, Sref)\n\n"
            "IMPORTANT :\n"
            "- Si une valeur n'est pas présente dans les documents, "
            "NE PAS l'inclure du tout. Ne jamais écrire 'non spécifié', 'non précisé', "
            "'N/A' ou similaire. Omets simplement cette donnée.\n"
            "- Si une valeur n'a PAS d'unité (ex: Bbio), écrire juste la valeur "
            "SANS mentionner '(sans unité)'. Ex: 'Bbio projet : 55.2'.\n"
        ),
        category="contrainte",
    ),
    SectionConfig(
        key="vent_pluie",
        label="Vent & Pluie",
        search_queries=[
            "classement AEV menuiseries zone vent",
            "zone vent pluie exposition DTU catégorie terrain",
        ],
        schema_type=None,
        prompt=(
            "Extrais UNIQUEMENT les classements réglementaires liés au vent et à la pluie : "
            "zone de vent, vitesse de référence, catégorie de terrain, exposition, "
            "zone de pluie, classement AEV des menuiseries, DTU applicables.\n\n"
            "Ne PAS inclure :\n"
            "- Détails de menuiseries (type, marque, joints, compriband, EPDM, jupes, pattes de fixation)\n"
            "- Étanchéité à l'air des liaisons menuiseries/maçonnerie\n"
            "- Grilles d'entrées d'air, calfeutrement\n"
            "- PV à transmettre, documents à fournir\n"
            "- Plomberie (tuyaux de descente, gouttières)\n"
            "- Terrassement ou autres travaux\n\n"
            "UNIQUEMENT les classements liés au VENT et à la PLUIE. "
            "Chaque detail doit concerner directement le vent ou la pluie. "
            "Si un élément ne parle pas de vent ou de pluie "
            "(ex: bruit, acoustique, thermique, type de menuiserie), NE PAS l'inclure.\n"
            "Si aucune donnée de classement vent/pluie n'est trouvée dans les documents, "
            "retourne un JSON avec des listes vides."
        ),
        category="contrainte",
        doc_types=[TYPE_CCTP],
    ),
    SectionConfig(
        key="sismique",
        label="Sismique",
        search_queries=[
            "zone sismicité catégorie sol PS-MI Eurocode 8",
            "sismique classe bâtiment zonage aléa",
        ],
        schema_type=None,
        prompt=(
            "Extrais UNIQUEMENT les données de classification sismique de la localisation : "
            "zone de sismicité (1 à 5), catégorie de sol (A à E), classe de bâtiment, "
            "règles applicables (PS-MI, Eurocode 8).\n\n"
            "IMPORTANT : ces données se trouvent généralement dans le lot gros-œuvre "
            "du CCTP ou dans les généralités.\n"
            "NE PAS inclure de détails constructifs (volumes de béton, chaînages, "
            "quantités de matériaux, isolations, réseaux). On cherche uniquement "
            "le classement sismique réglementaire du site.\n"
            "Si aucune donnée de classement sismique n'est trouvée, "
            "retourne un JSON avec des listes vides."
        ),
        category="contrainte",
        doc_types=[TYPE_CCTP],
    ),
    SectionConfig(
        key="contraintes_constructives",
        label="Contraintes constructives",
        search_queries=[
            "mitoyenneté accès chantier servitude sécurité",
            "nappe phréatique argiles retrait gonflement PLU",
        ],
        schema_type=None,
        prompt=(
            "Extrais les contraintes constructives du site et les obligations de sécurité :\n"
            "- Contraintes de site : mitoyenneté, accès chantier, nappe phréatique, "
            "retrait-gonflement argiles, servitudes, profondeur minimale de fondation, PLU\n"
            "- Sécurité chantier : protections obligatoires (garde-corps, étaiement, "
            "protection des trémies), règles d'accès, maintien du chantier\n\n"
            "IMPORTANT : NE PAS inclure de détails techniques de mise en œuvre "
            "(réseaux AEP, pénétrations en maçonnerie, chapes d'arase, enduits, "
            "canalisations, mortier). On cherche uniquement les contraintes du site "
            "et les obligations de sécurité, PAS les descriptions de travaux."
        ),
        category="contrainte",
        doc_types=[TYPE_CCTP],
    ),
]

DESCRIPTION_PROMPT = (
    "Tu es un économiste de la construction expert. "
    "À partir des résumés de sections ci-dessous, "
    "rédige une description SYNTHÉTIQUE du projet en 4 paragraphes courts.\n\n"
    "Structure EXACTE à suivre :\n"
    "- Paragraphe 1 : Type de bâtiment, niveaux, structure porteuse (matériau + épaisseur)\n"
    "- Paragraphe 2 : Fondations + couverture (charpente + matériau de couverture)\n"
    "- Paragraphe 3 : Isolation des murs (ITI ou ITE, juste le type)\n"
    "- Paragraphe 4 : Chauffage, ECS, VMC (type principal uniquement)\n\n"
    "EXEMPLE de résultat attendu :\n"
    '"""\n'
    "Le projet consiste en la construction d'une maison individuelle à deux niveaux "
    "(RDC + R+1), réalisée en maçonnerie d'agglomérés creux de 20 cm.\n\n"
    "Les fondations sont constituées de semelles filantes en béton armé. "
    "La toiture est réalisée en charpente traditionnelle, recevant une couverture en ardoises.\n\n"
    "Les murs extérieurs sont isolés par une isolation thermique par l'intérieur (ITI).\n\n"
    "Le bâtiment est équipé d'un chauffage par pompe à chaleur air/air, "
    "d'une production d'ECS par ballon thermodynamique "
    "et d'une VMC simple flux hygroréglable.\n"
    '"""\n\n'
    "NIVEAU DE DÉTAIL — Rester au même niveau de synthèse que l'exemple :\n"
    "- Structure : matériau + épaisseur, c'est tout. "
    "Pas de 'hourdés au mortier de ciment', pas de mode de pose.\n"
    "- Fondations : type uniquement (semelles filantes, radier...). "
    "Pas de détails sur le soubassement.\n"
    "- Couverture : charpente (traditionnelle/fermettes) + matériau (ardoises/tuiles). "
    "Pas d'essence de bois, pas de 'sur voliges'.\n"
    "- Isolation : ITI ou ITE, c'est tout. "
    "Pas de matériau isolant, pas d'épaisseur, pas de parement.\n"
    "- Chauffage : type de PAC ou chaudière + ECS + VMC. "
    "Pas d'émetteurs (ventilo-convecteurs), pas de marques.\n\n"
    "Règles :\n"
    "- Reprendre les termes EXACTS des résumés (ITI/ITE, air/air, ardoises...)\n"
    "- Si une info n'est pas disponible, omettre le paragraphe. "
    "Ne JAMAIS écrire 'non précisé'.\n"
    "- Ne PAS mentionner : garage, annexes, valeurs R/Uw, réglementation, marques.\n\n"
    "Réponds UNIQUEMENT avec le texte de la description, sans titre ni formatage."
)

SECTION_EXTRACTION_PROMPT = (
    "Tu es un économiste de la construction expert. "
    "À partir des extraits documentaires ci-dessous, extrais les informations techniques "
    "demandées au format JSON strict.\n\n"
    "MÉTHODE — Extraction par citation :\n"
    "1. D'abord, IDENTIFIE dans le contexte les passages pertinents pour la section demandée.\n"
    "2. CITE les termes exacts du document (matériaux, dimensions, valeurs).\n"
    "3. Structure ces citations dans le JSON ci-dessous.\n"
    "4. Si un terme n'apparaît PAS textuellement dans le contexte, NE L'INCLUS PAS.\n\n"
    "Règles :\n"
    "- FIDÉLITÉ AU TEXTE SOURCE : utilise les termes EXACTS des documents. "
    "Ne JAMAIS remplacer un terme précis par un terme générique "
    "(ex: ne pas écrire 'bloc porteur' si le document dit 'agglomérés creux de 20cm', "
    "ne pas écrire 'isolant' si le document dit 'laine de verre 100mm').\n"
    "- KPIs : 2-5 valeurs chiffrées clés TRÈS COURTES (max 25 caractères chacune, "
    'format "valeur unité" ex: "R = 4.0 m²K/W", "Ø 80mm zinc", "Pente 30%"). '
    "Maximum 5 KPIs, moins si peu de données.\n"
    "- Description : 1-2 phrases techniques résumant le système en utilisant les termes exacts.\n"
    "- Details : 4-8 points techniques précis (type, composition, dimensions unitaires). "
    "Chaque detail doit pouvoir être retrouvé dans le contexte source.\n"
    "- Ne JAMAIS inclure de quantités, métrés ou longueurs cumulées "
    "(pas de m3, m2, ml, pas de longueurs par file ou par travée). "
    "Seules les dimensions unitaires (section, épaisseur, hauteur) sont acceptées.\n"
    "- Si une donnée n'est pas présente dans les documents, NE PAS écrire "
    '"non spécifié", "non précisé" ou similaire. Omets simplement le champ.\n'
    "- Ne JAMAIS inventer, déduire ou généraliser. Seules les infos explicites comptent.\n"
    "- Si un schéma est demandé, extrais les paramètres dimensionnels exacts\n\n"
    "STRUCTURE JSON OBLIGATOIRE — tu DOIS retourner EXACTEMENT cette structure, "
    "avec ces 4 clés au premier niveau. JAMAIS d'objet imbriqué, JAMAIS de tableau "
    "d'objets, JAMAIS de sous-catégories. Si plusieurs variantes existent "
    "(ex: PVC et aluminium), FUSIONNE-les dans une seule description et des details combinés :\n"
    "{\n"
    '  "description": "...",\n'
    '  "kpis": ["...", "..."],\n'
    '  "details": ["...", "..."],\n'
    '  "schema": {"schema_type": "...", "params": {...}} | null\n'
    "}\n\n"
    "Les natures valides pour les couches de schéma multicouche sont : "
    "beton, beton_arme, isolant_thermique, isolant_acoustique, gravier, sable, "
    "terre, plaque_platre, enduit, bois, acier, carrelage, chape, hourdis, "
    "film_pe, pare_vapeur, ecran_sous_toiture, tuile, ardoise, zinc, membrane_etanche.\n\n"
    "Pour les schémas multicouche (dallage, mur, plancher, charpente), "
    "les couches doivent être ordonnées du haut vers le bas (ou de l'extérieur vers l'intérieur) "
    'avec le format : [{"nom": "...", "epaisseur": "X cm", "nature": "..."}]'
)


def _normalize_section_json(data: dict[str, object]) -> dict[str, object]:
    """Flatten nested LLM responses into the expected {description, kpis, details, schema} format.

    Handles cases where the LLM returns sub-categories instead of a flat structure,
    e.g. {"menuiseries": [{...}, {...}]} or {"contraintes_site": {...}, "securite_chantier": {...}}.
    """
    if "description" in data and isinstance(data.get("description"), str):
        return data

    merged_desc: list[str] = []
    merged_kpis: list[str] = []
    merged_details: list[str] = []
    merged_schema = None

    def _extract(obj: dict[str, object]) -> None:
        nonlocal merged_schema
        desc = obj.get("description", "")
        if isinstance(desc, str) and desc:
            merged_desc.append(desc)
        kpis = obj.get("kpis", [])
        if isinstance(kpis, list):
            merged_kpis.extend(str(k) for k in kpis)
        details = obj.get("details", [])
        if isinstance(details, list):
            merged_details.extend(str(d) for d in details)
        if merged_schema is None and isinstance(obj.get("schema"), dict):
            merged_schema = obj["schema"]

    for value in data.values():
        if isinstance(value, dict):
            _extract(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _extract(item)

    if not merged_desc and not merged_kpis and not merged_details:
        return data

    logger.info("[Summary] Normalized nested JSON structure into flat format")
    return {
        "description": " ".join(merged_desc),
        "kpis": merged_kpis[:5],
        "details": merged_details,
        "schema": merged_schema,
    }


def _repair_json(raw: str) -> dict[str, object] | None:
    """Attempt to repair truncated JSON from LLM responses.

    Trims a growing suffix off the end and retries with closing brackets,
    from the widest trim down, so the shortest successful repair wins and
    the recovered object is the smallest available. Valid JSON passed in
    still returns None, since every attempt removes at least one character.
    """
    for i in range(min(len(raw), 200), 0, -1):
        candidate = raw[: len(raw) - i]
        for suffix in ("]}", '"]}', '"}'):
            try:
                result = json.loads(candidate + suffix)
                if isinstance(result, dict):
                    logger.info("[Summary] JSON repaired successfully")
                    return result
            except json.JSONDecodeError:
                continue
    logger.error("[Summary] JSON repair failed. Raw (last 200 chars): %s", raw[-200:])
    return None


async def get_summary(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> ProjectSummary | None:
    """Fetch the cached summary for a project (tenant-isolated via project FK)."""
    stmt = (
        select(ProjectSummary)
        .join(Project, ProjectSummary.project_id == Project.id)
        .where(ProjectSummary.project_id == project_id, Project.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_summary_status(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> SummaryStatusRead:
    """Check whether the project has documents and/or a cached summary."""
    doc_count_stmt = (
        select(func.count())
        .select_from(Document)
        .join(Project, Document.project_id == Project.id)
        .where(Document.project_id == project_id, Project.tenant_id == tenant_id)
    )
    doc_count = (await db.execute(doc_count_stmt)).scalar_one()

    summary = await get_summary(db, tenant_id=tenant_id, project_id=project_id)

    return SummaryStatusRead(
        has_documents=doc_count > 0,
        has_summary=summary is not None and summary.status != "generating",
        status=summary.status if summary else None,
    )


async def generate_summary_stream(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> AsyncGenerator[str, None]:
    """Generate a project summary via multi-pass RAG, streaming progress as SSE."""
    # ── Step 1: Verify project has documents ──
    doc_count_stmt = (
        select(func.count())
        .select_from(Document)
        .join(Project, Document.project_id == Project.id)
        .where(Document.project_id == project_id, Project.tenant_id == tenant_id)
    )
    doc_count = (await db.execute(doc_count_stmt)).scalar_one()
    if doc_count == 0:
        yield _sse({"type": "error", "message": "Aucun document dans le projet"})
        yield "data: [DONE]\n\n"
        return

    chunk_count_stmt = (
        select(func.count())
        .select_from(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .join(Project, Document.project_id == Project.id)
        .where(Document.project_id == project_id, Project.tenant_id == tenant_id)
    )
    chunk_count = (await db.execute(chunk_count_stmt)).scalar_one()
    search_limit, max_context_chars = _get_search_params(chunk_count)
    logger.info(
        "[Summary] Project %s | %d docs, %d chunks | search_limit=%d, max_context=%d",
        project_id,
        doc_count,
        chunk_count,
        search_limit,
        max_context_chars,
    )

    # ── Step 2: Create/update summary row ──
    summary = await get_summary(db, tenant_id=tenant_id, project_id=project_id)
    if summary is None:
        summary = ProjectSummary(project_id=project_id, status="generating")
        db.add(summary)
    else:
        summary.status = "generating"
        summary.data_json = None
        summary.error_message = None
    await db.commit()
    await db.refresh(summary)

    total_sections = len(SECTION_CONFIGS)

    # ── Step 3: Batch embed all queries ──
    all_queries: list[str] = []
    query_index_map: list[tuple[int, int]] = []
    for si, cfg in enumerate(SECTION_CONFIGS):
        for qi, q in enumerate(cfg.search_queries):
            all_queries.append(q)
            query_index_map.append((si, qi))

    try:
        all_vectors = await embed_texts(all_queries)
    except Exception as exc:
        logger.exception("Failed to embed queries")
        summary.status = "error"
        summary.error_message = f"Embedding failed: {exc}"
        await db.commit()
        yield _sse({"type": "error", "message": "Erreur lors de l'embedding des requêtes"})
        yield "data: [DONE]\n\n"
        return

    section_vectors: list[list[list[float]]] = [[] for _ in SECTION_CONFIGS]
    for idx, (si, _qi) in enumerate(query_index_map):
        section_vectors[si].append(all_vectors[idx])

    # ── Step 4 & 5: Search + extract per section (with concurrency limit) ──
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    section_results: list[dict[str, object] | None] = [None] * total_sections
    section_errors: list[str | None] = [None] * total_sections

    async def process_section(si: int) -> None:
        async with semaphore:
            cfg = SECTION_CONFIGS[si]
            try:
                scored_chunks: list[tuple[str, float]] = []
                seen_ids: set[str] = set()
                seen_texts: set[str] = set()
                for vec in section_vectors[si]:
                    must_conditions = [
                        FieldCondition(
                            key="tenant_id",
                            match=MatchValue(value=str(tenant_id)),
                        ),
                        FieldCondition(
                            key="project_id",
                            match=MatchValue(value=str(project_id)),
                        ),
                    ]
                    if cfg.doc_types:
                        must_conditions.append(
                            FieldCondition(
                                key="type",
                                match=MatchAny(any=cfg.doc_types),
                            )
                        )
                    must_not_conditions = []
                    if cfg.exclude_content_types:
                        for ct in cfg.exclude_content_types:
                            must_not_conditions.append(
                                FieldCondition(
                                    key="content_type",
                                    match=MatchValue(value=ct),
                                )
                            )
                    qfilter = Filter(
                        must=must_conditions,
                        must_not=must_not_conditions or None,
                    )
                    hits = await qdrant_client.search(
                        collection_name=COLLECTION_NAME,
                        query_vector=vec,
                        query_filter=qfilter,
                        limit=search_limit,
                        score_threshold=0.35,
                    )
                    query_text = (
                        cfg.search_queries[section_vectors[si].index(vec)]
                        if vec in section_vectors[si]
                        else "?"
                    )
                    if hits:
                        scores = [f"{h.score:.3f}" for h in hits]
                        logger.info(
                            "[Summary] %s | query=%r | %d hits | scores=%s",
                            cfg.key,
                            query_text,
                            len(hits),
                            scores,
                        )
                        for h in hits[:2]:
                            p = h.payload or {}
                            logger.info(
                                "[Summary]   -> score=%.3f type=%s content_type=%s file=%s",
                                h.score,
                                p.get("type"),
                                p.get("content_type"),
                                p.get("filename"),
                            )
                    else:
                        debug_hits = await qdrant_client.search(
                            collection_name=COLLECTION_NAME,
                            query_vector=vec,
                            query_filter=qfilter,
                            limit=3,
                        )
                        if debug_hits:
                            debug_scores = [f"{h.score:.3f}" for h in debug_hits]
                            logger.warning(
                                "[Summary] %s | query=%r | 0 hits above 0.35 | "
                                "best scores WITHOUT threshold=%s | types=%s",
                                cfg.key,
                                query_text,
                                debug_scores,
                                [h.payload.get("type") for h in debug_hits if h.payload],
                            )
                        else:
                            logger.warning(
                                "[Summary] %s | query=%r | 0 hits even without threshold",
                                cfg.key,
                                query_text,
                            )

                    for hit in hits:
                        point_id = str(hit.id)
                        if point_id not in seen_ids:
                            seen_ids.add(point_id)
                            payload = hit.payload or {}
                            text = payload.get("text", "")
                            if text:
                                text_stripped = re.sub(
                                    r"^[\d]+(?:\.[\d]+)*\.?\s*", "", text.strip()
                                )
                                text_key = text_stripped.lower()[:200]
                                if text_key in seen_texts:
                                    continue
                                seen_texts.add(text_key)
                                source_info = payload.get("filename", "")
                                if payload.get("lot"):
                                    source_info += f" | {payload['lot']}"
                                scored_chunks.append((f"[{source_info}]\n{text}", hit.score))

                if not scored_chunks:
                    logger.warning(
                        "[Summary] %s | SKIPPED — no context chunks found",
                        cfg.key,
                    )
                    section_results[si] = None
                    section_errors[si] = "no_context"
                    return

                scored_chunks.sort(key=lambda x: x[1], reverse=True)
                context_block = ""
                used_count = 0
                for chunk_text, _score in scored_chunks:
                    candidate = (
                        context_block + "\n\n---\n\n" + chunk_text if context_block else chunk_text
                    )
                    if len(candidate) > max_context_chars:
                        break
                    context_block = candidate
                    used_count += 1

                logger.info(
                    "[Summary] %s | %d chunks found, %d used, %d chars (max %d) | coverage=%.1f%%",
                    cfg.key,
                    len(scored_chunks),
                    used_count,
                    len(context_block),
                    max_context_chars,
                    (used_count / len(scored_chunks) * 100) if scored_chunks else 0,
                )

                schema_instruction = ""
                if cfg.schema_type:
                    schema_instruction = (
                        f'\n\nSchéma demandé : type="{cfg.schema_type}". '
                        f'Extrais les paramètres dans le champ "schema".'
                    )

                response = await mistral_client.chat.complete_async(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": SECTION_EXTRACTION_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"Section : {cfg.label}\n\n"
                                f"Instructions spécifiques :\n{cfg.prompt}"
                                f"{schema_instruction}\n\n"
                                f"Contexte documentaire :\n\n{context_block}"
                            ),
                        },
                    ],
                    temperature=0.0,
                    max_tokens=1500,
                    response_format={"type": "json_object"},
                )

                raw = response.choices[0].message.content  # type: ignore[union-attr]
                if not raw:
                    section_errors[si] = "empty_llm_response"
                    return

                logger.debug(
                    "[Summary] %s | raw LLM response (%d chars): %s",
                    cfg.key,
                    len(raw),
                    raw[:2000],
                )

                try:
                    data = json.loads(raw.strip())
                except json.JSONDecodeError:
                    logger.warning(
                        "[Summary] %s | JSON parse failed, attempting repair. Raw length=%d, "
                        "finish_reason=%s",
                        cfg.key,
                        len(raw),
                        response.choices[0].finish_reason,  # type: ignore[union-attr]
                    )
                    data = _repair_json(raw.strip())
                    if data is None:
                        section_errors[si] = "json_parse_error"
                        return
                data = _normalize_section_json(data)
                logger.info(
                    "[Summary] %s | LLM result: description=%d chars, kpis=%s, details=%d, schema=%s",
                    cfg.key,
                    len(data.get("description", "")),
                    data.get("kpis", []),
                    len(data.get("details", [])),
                    "yes" if data.get("schema") else "no",
                )
                section_results[si] = data

            except Exception as exc:
                logger.exception("Section %s failed", cfg.label)
                section_errors[si] = str(exc)

    tasks = [asyncio.create_task(process_section(si)) for si in range(total_sections)]
    for si, task in enumerate(tasks):
        await task
        cfg = SECTION_CONFIGS[si]
        status = "done" if section_results[si] is not None else "error"
        if section_errors[si] == "no_context":
            status = "skipped"
        yield _sse(
            {
                "type": "progress",
                "section": cfg.label,
                "index": si + 1,
                "total": total_sections,
                "status": status,
            }
        )

    # ── Step 7: Generate project description from section summaries only ──
    description = ""
    try:
        section_summaries: list[str] = []
        for si2, cfg2 in enumerate(SECTION_CONFIGS):
            data2 = section_results[si2]
            if data2 is None:
                continue
            parts: list[str] = []
            desc2 = data2.get("description", "")
            if isinstance(desc2, str) and desc2:
                parts.append(desc2)
            kpis2 = data2.get("kpis", [])
            if isinstance(kpis2, list) and kpis2:
                parts.append("KPIs: " + ", ".join(str(k) for k in kpis2))
            details2 = data2.get("details", [])
            if isinstance(details2, list) and details2:
                parts.append("Détails: " + " | ".join(str(d) for d in details2))
            if parts:
                section_summaries.append(f"[{cfg2.label}]\n" + "\n".join(parts))

        if section_summaries:
            context = "\n\n".join(section_summaries)
            if len(context) > max_context_chars:
                context = context[:max_context_chars]

            resp = await mistral_client.chat.complete_async(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": DESCRIPTION_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Voici les résumés techniques extraits des sections du projet. "
                            "Rédige la description en utilisant UNIQUEMENT ces données. "
                            "Ne modifie PAS les termes techniques (matériaux, types d'équipements).\n\n"
                            f"{context}"
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=400,
            )
            description = (resp.choices[0].message.content or "").strip()  # type: ignore[union-attr]
    except Exception:
        logger.exception("Description generation failed")
        description = "Description non disponible."

    yield _sse(
        {
            "type": "progress",
            "section": "Description",
            "index": total_sections + 1,
            "total": total_sections + 1,
            "status": "done",
        }
    )

    # ── Step 8: Assemble ProjectSummaryData ──
    constructif_items: list[SystemeConstructifItem] = []
    contrainte_items: list[ContrainteItem] = []

    for si, cfg in enumerate(SECTION_CONFIGS):
        data = section_results[si]
        if data is None:
            continue

        kpis = data.get("kpis", [])
        if not isinstance(kpis, list):
            kpis = []
        kpis = [
            str(k)
            for k in kpis
            if isinstance(k, str)
            and not any(skip in k.lower() for skip in ("non spécifié", "non précisé", "n/a"))
        ][:5]
        details = data.get("details", [])
        if not isinstance(details, list):
            details = []
        cleaned_details: list[str] = []
        for d in details:
            if not isinstance(d, str):
                continue
            d_lower = d.strip().lower()
            if d_lower in ("non spécifié", "non précisé", "n/a", "non précisée", "non spécifiée"):
                continue
            if re.search(
                r"non\s+d[ée]taill[ée]|non\s+disponible|non\s+(?:sp[ée]cifi|pr[ée]cis)[ée]?[es]?\s+dans",
                d_lower,
            ):
                continue
            if re.search(r"à\s+(?:confirmer|valider)|selon\s+étude", d_lower):
                continue
            if d_lower.startswith("localisation"):
                continue
            cleaned = re.sub(
                r"\s*\([^)]*(?:non\s+(?:précis|spécifi)[ée]?[es]?|à\s+(?:confirmer|valider)|selon\s+étude)[^)]*\)",
                "",
                d,
                flags=re.IGNORECASE,
            ).strip()
            if cleaned:
                cleaned_details.append(cleaned)
        details = cleaned_details
        desc = data.get("description", "")
        if not isinstance(desc, str):
            desc = ""

        if cfg.category == "contrainte" and not kpis and not details:
            continue

        if cfg.category == "constructif":
            schema_data = None
            if cfg.schema_type and isinstance(data.get("schema"), dict):
                raw_schema = data["schema"]
                s_type = raw_schema.get("schema_type", cfg.schema_type)
                raw_params = raw_schema.get("params", {})
                if isinstance(raw_params, dict):
                    params: dict[str, str] = {}
                    for k, v in raw_params.items():
                        if isinstance(v, list):
                            params[k] = json.dumps(v, ensure_ascii=False)
                        elif v is not None:
                            params[k] = str(v)
                    if params:
                        schema_data = SummarySchemaData(schema_type=str(s_type), params=params)

            constructif_items.append(
                SystemeConstructifItem(
                    label=cfg.label,
                    description=str(desc),
                    kpis=kpis,
                    details=details,
                    schema_=schema_data,
                )
            )
        else:
            contrainte_items.append(
                ContrainteItem(
                    label=cfg.label,
                    kpis=kpis,
                    details=details,
                )
            )

    summary_data = ProjectSummaryData(
        description=description,
        systeme_constructif=constructif_items,
        contraintes=contrainte_items,
    )

    total_ok = sum(1 for r in section_results if r is not None)
    if total_ok == 0:
        final_status = "error"
        summary.error_message = "Aucune section n'a pu être extraite"
    elif total_ok < total_sections:
        final_status = "partial"
    else:
        final_status = "done"

    summary.status = final_status
    summary.data_json = summary_data.model_dump_json()
    summary.generated_at = datetime.now(UTC)
    await db.commit()

    # ── Step 9: Yield final result ──
    yield _sse(
        {
            "type": "complete",
            "summary": json.loads(summary_data.model_dump_json(by_alias=True)),
            "status": final_status,
        }
    )
    yield "data: [DONE]\n\n"


def _sse(data: dict[str, object]) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
