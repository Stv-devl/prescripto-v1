import { AlertTriangle, RotateCcw, Home } from "lucide-react";
import { useRouteError, isRouteErrorResponse, Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";

export function RouteErrorPage(): React.ReactElement {
  const error = useRouteError();

  let title = "Une erreur inattendue est survenue";
  let description =
    "L'application a rencontré un problème. Vous pouvez réessayer ou retourner à l'accueil.";

  if (isRouteErrorResponse(error)) {
    if (error.status === 404) {
      title = "Page introuvable";
      description = "La page que vous recherchez n'existe pas ou a été déplacée.";
    } else {
      title = `Erreur ${error.status}`;
    }
  }

  console.error("Route error:", error);

  return (
    <div
      role="alert"
      className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[hsl(var(--background))] p-8 text-center"
    >
      <AlertTriangle className="h-12 w-12 text-red-400" />
      <h1 className="text-lg font-semibold text-[hsl(var(--foreground))]">
        {title}
      </h1>
      <p className="max-w-md text-sm text-muted-foreground">{description}</p>
      <div className="flex gap-3">
        <Button
          variant="outline"
          onClick={() => {
            window.location.reload();
          }}
        >
          <RotateCcw className="mr-2 h-4 w-4" />
          Réessayer
        </Button>
        <Button variant="outline" asChild>
          <Link to="/projects">
            <Home className="mr-2 h-4 w-4" />
            Retour aux projets
          </Link>
        </Button>
      </div>
    </div>
  );
}
