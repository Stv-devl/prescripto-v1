import { LegalLayout } from "@/components/layout/LegalLayout";

/**
 * Terms of service page — Conditions générales d'utilisation.
 */
export function TermsPage(): React.ReactElement {
  return (
    <LegalLayout
      title="Conditions générales d'utilisation"
      subtitle="Les règles qui encadrent l'utilisation de la plateforme Prescripto."
      updatedAt="4 mars 2026"
    >
      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          1. Objet
        </h2>
        <p>
          Les présentes conditions générales régissent l'utilisation de la
          plateforme Prescripto, une GED intelligente destinée aux économistes
          de la construction. Toute utilisation du service implique
          l'acceptation pleine et entière des présentes conditions.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          2. Description du service
        </h2>
        <p>
          Prescripto permet l'upload, le classement automatique, la recherche
          intelligente et l'analyse de documents liés à des projets de
          construction. Le service utilise l'intelligence artificielle pour
          indexer et retrouver l'information dans vos documents.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          3. Inscription et compte
        </h2>
        <ul className="list-disc list-inside space-y-1.5 ml-2">
          <li>
            L'utilisateur s'engage à fournir des informations exactes lors de
            l'inscription
          </li>
          <li>Chaque compte est personnel et ne peut être partagé</li>
          <li>
            L'utilisateur est responsable de la confidentialité de ses
            identifiants
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          4. Abonnement et paiement
        </h2>
        <p>
          Le service est proposé sous forme d'abonnement mensuel ou annuel. Les
          tarifs en vigueur sont affichés sur la page Tarifs du site. Tout mois
          entamé est dû. L'abonnement peut être résilié à tout moment depuis
          l'espace personnel.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          5. Propriété intellectuelle
        </h2>
        <p>
          Les documents uploadés restent la propriété exclusive de
          l'utilisateur. Prescripto ne revendique aucun droit sur vos contenus.
          La plateforme, son code, son design et sa marque sont la propriété de
          [Nom de la société].
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          6. Responsabilité
        </h2>
        <p>
          Les réponses générées par l'IA sont fournies à titre indicatif et ne
          sauraient se substituer à l'expertise professionnelle de l'économiste.
          L'utilisateur reste seul responsable des décisions prises sur la base
          des informations fournies par le service.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          7. Résiliation
        </h2>
        <p>
          L'utilisateur peut résilier son abonnement à tout moment. L'accès au
          service reste actif jusqu'à la fin de la période payée. En cas de
          violation des présentes conditions, Prescripto se réserve le droit de
          suspendre ou supprimer un compte sans préavis.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          8. Droit applicable
        </h2>
        <p>
          Les présentes conditions sont régies par le droit français. En cas de
          litige, les tribunaux compétents seront ceux du ressort du siège
          social de la société éditrice.
        </p>
      </section>
    </LegalLayout>
  );
}
