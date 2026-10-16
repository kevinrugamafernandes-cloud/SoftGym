import { useMemo } from "react";
import { useAuth } from "./AuthContext";
import { hasPermission, type Permission } from "./permissions";

/** `const { can } = usePermissions(); can("members.edit")` */
export function usePermissions() {
  const { user } = useAuth();
  const role = user?.role ?? null;
  return useMemo(
    () => ({ role, can: (permission: Permission) => hasPermission(role, permission) }),
    [role]
  );
}
