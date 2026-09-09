import { Button } from "@/components/ui/Button";

interface AccountSectionProps {
  tenantName: string | null;
  tenantPlan: string | null;
  onChangePassword: () => void;
}

const planLabels: Record<string, string> = {
  free: "Gratuit",
  pro: "Pro",
  enterprise: "Enterprise",
};

export function AccountSection({
  tenantName,
  tenantPlan,
  onChangePassword,
}: AccountSectionProps) {
  const planLabel = tenantPlan ? (planLabels[tenantPlan] ?? tenantPlan) : "—";

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold text-[hsl(var(--foreground))]">
        Compte
      </h2>

      <div className="space-y-5 rounded-lg bg-[hsl(var(--secondary))] p-6">
        <div className="space-y-2">
          <p className="text-sm font-medium text-[hsl(var(--foreground))]">
            Société
          </p>
          <p className="text-[hsl(var(--muted-foreground))]">
            {tenantName ?? "—"}
          </p>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium text-[hsl(var(--foreground))]">
            Abonnement
          </p>
          <span className="inline-block rounded-full bg-[hsl(var(--primary))]/15 px-3 py-1 text-sm font-medium text-[hsl(var(--primary))]">
            {planLabel}
          </span>
        </div>

        <div className="pt-2">
          <Button variant="outline" onClick={onChangePassword}>
            Changer le mot de passe
          </Button>
        </div>
      </div>
    </section>
  );
}
