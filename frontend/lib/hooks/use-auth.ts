import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, tokenManager } from '@/lib/api-client';
import type { LoginRequest, RegisterRequest } from '@/types/api';
import { useRouter } from 'next/navigation';

/**
 * Hook to handle user login
 */
export function useLogin() {
  const router = useRouter();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (credentials: LoginRequest) => api.auth.login(credentials),
    onSuccess: () => {
      // Clear all queries on login
      queryClient.clear();
      // Redirect to dashboard
      router.push('/dashboard');
    },
  });
}

/**
 * Hook to handle user registration
 */
export function useRegister() {
  const router = useRouter();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userData: RegisterRequest) => api.auth.register(userData),
    onSuccess: () => {
      // Clear all queries on registration
      queryClient.clear();
      // Redirect to dashboard
      router.push('/dashboard');
    },
  });
}

/**
 * Hook to handle user logout
 */
export function useLogout() {
  const router = useRouter();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.auth.logout(),
    onSuccess: () => {
      // Clear all queries on logout
      queryClient.clear();
      // Redirect to login
      router.push('/login');
    },
  });
}

/**
 * Hook to check authentication status
 */
export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isMounted, setIsMounted] = useState<boolean>(false);
  const logout = useLogout();

  useEffect(() => {
    setIsMounted(true);
    setIsAuthenticated(tokenManager.isAuthenticated());
  }, []);

  return {
    isAuthenticated: isMounted ? isAuthenticated : false,
    token: isMounted ? tokenManager.getToken() : null,
    logout,
    isMounted,
  };
}
