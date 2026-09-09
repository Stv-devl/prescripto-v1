import { PublicFooter } from "./PublicFooter";
import { PublicNavbar } from "./PublicNavbar";

/**
 * Public layout container with navigation and footer.
 * Used for unauthenticated pages (landing, auth, legal).
 */
export function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <div className="min-h-screen bg-[#1C1C1C]">
      <PublicNavbar />
      <main className="flex-1">{children}</main>
      <PublicFooter />
    </div>
  );
}
