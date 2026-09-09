import { LegalLayout } from "@/components/layout/LegalLayout";

/**
 * Cookies policy page — Politique de cookies.
 */
export function CookiesPage(): React.ReactElement {
  return (
    <LegalLayout
      title="Politique de cookies"
      subtitle="Quels cookies nous utilisons et comment vous pouvez les gérer."
      updatedAt="4 mars 2026"
    >
      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          1. Qu'est-ce qu'un cookie ?
        </h2>
        <p>
          Un cookie est un petit fichier texte déposé sur votre navigateur lors
          de la visite d'un site web. Il permet de stocker des informations
          relatives à votre navigation.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          2. Cookies utilisés par Prescripto
        </h2>

        <div className="overflow-x-auto rounded-xl border border-[#F5F5F5]/10">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#F5F5F5]/5">
                <th className="py-3.5 px-4 text-[#F5F5F5] font-semibold text-sm">
                  Cookie
                </th>
                <th className="py-3.5 px-4 text-[#F5F5F5] font-semibold text-sm">
                  Finalité
                </th>
                <th className="py-3.5 px-4 text-[#F5F5F5] font-semibold text-sm">
                  Durée
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F5F5F5]/5">
              <tr>
                <td className="py-3 px-4 font-mono text-xs text-[#FFC300]">
                  auth_token
                </td>
                <td className="py-3 px-4">
                  Authentification et maintien de session
                </td>
                <td className="py-3 px-4 whitespace-nowrap">7 jours</td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-mono text-xs text-[#FFC300]">
                  refresh_token
                </td>
                <td className="py-3 px-4">
                  Renouvellement automatique de session
                </td>
                <td className="py-3 px-4 whitespace-nowrap">30 jours</td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-mono text-xs text-[#FFC300]">
                  cookie_consent
                </td>
                <td className="py-3 px-4">
                  Mémorisation de votre choix de cookies
                </td>
                <td className="py-3 px-4 whitespace-nowrap">12 mois</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          3. Cookies tiers
        </h2>
        <p>
          Prescripto n'utilise aucun cookie publicitaire ni tracker tiers. Nous
          n'intégrons aucun service de suivi comportemental (Google Analytics,
          Facebook Pixel, etc.).
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          4. Gestion des cookies
        </h2>
        <p>
          Vous pouvez à tout moment modifier vos préférences de cookies depuis
          les paramètres de votre navigateur :
        </p>
        <ul className="list-disc list-inside space-y-1.5 ml-2">
          <li>
            <strong className="text-[#F5F5F5]">Chrome</strong> : Paramètres &gt;
            Confidentialité et sécurité &gt; Cookies
          </li>
          <li>
            <strong className="text-[#F5F5F5]">Firefox</strong> : Paramètres
            &gt; Vie privée et sécurité &gt; Cookies
          </li>
          <li>
            <strong className="text-[#F5F5F5]">Safari</strong> : Préférences
            &gt; Confidentialité &gt; Cookies
          </li>
        </ul>
        <p>
          La désactivation des cookies essentiels peut empêcher le bon
          fonctionnement du service.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg md:text-xl font-semibold text-[#F5F5F5]">
          5. Contact
        </h2>
        <p>
          Pour toute question relative à notre utilisation des cookies,
          contactez-nous à{" "}
          <a
            href="mailto:contact@prescripto.fr"
            className="text-[#FFC300] hover:underline"
          >
            contact@prescripto.fr
          </a>
          .
        </p>
      </section>
    </LegalLayout>
  );
}
