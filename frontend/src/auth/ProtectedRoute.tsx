import React from 'react';
import { useAuth } from './AuthContext';
import { UserRole } from '../shared/types';
import { ErrorMessage } from '../shared/ui/ErrorMessage';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: UserRole;
  onUnauthorized?: () => void;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRole,
}) => {
  const { isAuthenticated, role } = useAuth();

  if (!isAuthenticated) {
    return <ErrorMessage message="Please log in to access this page." />;
  }

  if (requiredRole && role !== requiredRole) {
    return (
      <ErrorMessage
        message={`Access Denied: This area requires the ${requiredRole} role. You are currently logged in as ${role}.`}
      />
    );
  }

  return <>{children}</>;
};
