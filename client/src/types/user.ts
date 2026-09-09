export interface User {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
  first_name: string | null;
  last_name: string | null;
  tenant_name: string | null;
  tenant_plan: string | null;
  created_at: string;
}
