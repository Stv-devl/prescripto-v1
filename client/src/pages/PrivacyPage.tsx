import { LegalLayout } from "@/components/layout/LegalLayout";

/**
 * Privacy policy page — Politique de confidentialité.
 */
export function PrivacyPage(): React.ReactElement {
  return (
    <LegalLayout
      title="Politique de confidentialité"
      subtitle="Comment nous collectons, utilisons et protégeons vos données personnelles."
      updatedAt="4 mars 2026"
    >
      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          1. Responsable du traitement
        </h2>
        <p>
          Prescripto, édité par [Nom de la société], dont le siège social est
          situé à [Adresse]. Contact :{" "}
          <a
            href="mailto:contact@prescripto.fr"
            className="text-[#FFC300] hover:underline"
          >
            contact@prescripto.fr
          </a>
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          2. Données collectées
        </h2>
        <p>Nous collectons les données suivantes :</p>
        <ul className="list-disc list-inside space-y-1.5 ml-2">
          <li>
            <strong className="text-[#F5F5F5]">Compte utilisateur</strong> :
            nom, prénom, adresse e-mail, mot de passe (hashé)
          </li>
          <li>
            <strong className="text-[#F5F5F5]">Données d'usage</strong> :
            documents uploadés, recherches effectuées, conversations
          </li>
          <li>
            <strong className="text-[#F5F5F5]">Données techniques</strong> :
            adresse IP, type de navigateur, pages consultées
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          3. Finalités du traitement
        </h2>
        <ul className="list-disc list-inside space-y-1.5 ml-2">
          <li>Fourniture et amélioration du service Prescripto</li>
          <li>Gestion de votre compte et de votre abonnement</li>
          <li>Indexation et recherche intelligente dans vos documents</li>
          <li>Support client et communication</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          4. Hébergement et souveraineté
        </h2>
        <p>
          Vos données sont hébergées en France sur des serveurs OVH. Le
          traitement IA est assuré par Mistral AI (Paris). Aucune donnée ne
          transite hors de l'Union européenne.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          5. Durée de conservation
        </h2>
        <p>
          Vos données sont conservées pendant la durée de votre abonnement
          actif, puis supprimées dans un délai de 30 jours après clôture de
          votre compte, sauf obligation légale contraire.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          6. Vos droits
        </h2>
        <p>
          Conformément au RGPD, vous disposez d'un droit d'accès, de
          rectification, de suppression, de portabilité et d'opposition. Pour
          exercer ces droits, contactez-nous à{" "}
          <a
            href="mailto:contact@prescripto.fr"
            className="text-[#FFC300] hover:underline"
          >
            contact@prescripto.fr
          </a>
          .
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          7. Partage des données
        </h2>
        <p>
          Nous ne vendons ni ne partageons vos données personnelles avec des
          tiers, à l'exception des sous-traitants nécessaires au fonctionnement
          du service (hébergement, IA) qui sont soumis aux mêmes obligations de
          confidentialité.
        </p>
      </section>
    </LegalLayout>
  );
}
