import { useState } from "react";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { useAuthStore } from "@/lib/store/authStore";
import { AccountSection } from "../components/AccountSection";
import { ChangePasswordModal } from "../components/ChangePasswordModal";
import { ProfileSection } from "../components/ProfileSection";

export function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const [showPasswordModal, setShowPasswordModal] = useState(false);

  if (!user) {
    return (
      <main className="flex items-center justify-center p-6">
        <LoadingSpinner />
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl space-y-8 p-6">
      <h1 className="text-2xl font-bold text-[hsl(var(--foreground))]">
        Paramètres
      </h1>

      <ProfileSection
        firstName={user.first_name}
        lastName={user.last_name}
        email={user.email}
      />

      <AccountSection
        tenantName={user.tenant_name}
        tenantPlan={user.tenant_plan}
        onChangePassword={() => setShowPasswordModal(true)}
      />

      {showPasswordModal && (
        <ChangePasswordModal onClose={() => setShowPasswordModal(false)} />
      )}
    </main>
  );
}
