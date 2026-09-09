import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";

interface DocumentsSectionStateProps {
  isDocsPending: boolean;
  docsError: Error | null;
  hasDocuments: boolean;
  hasFolders: boolean;
}

/** The pending/error/empty-global states shown above the documents toolbar. */
export function DocumentsSectionState({
  isDocsPending,
  docsError,
  hasDocuments,
  hasFolders,
}: DocumentsSectionStateProps) {
  return (
    <>
      {isDocsPending && (
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      )}

      {docsError && <ErrorMessage error={docsError} />}

      {!isDocsPending && !docsError && !hasDocuments && !hasFolders && (
        <EmptyState message="Aucun document. Ajoutez un fichier ci-dessus." />
      )}
    </>
  );
}
