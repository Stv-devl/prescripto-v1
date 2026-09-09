import { Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";

/**
 * 404 page displayed when no route matches.
 */
export function NotFoundPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <h1 className="text-6xl font-bold text-gray-900">404</h1>
      <p className="mt-4 text-xl text-gray-600">Page non trouvée</p>
      <p className="mt-2 text-gray-500">
        La page que vous recherchez n'existe pas.
      </p>
      <Link to="/" className="mt-8">
        <Button>Retour à l'accueil</Button>
      </Link>
    </main>
  );
}
