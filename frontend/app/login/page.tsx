"use client";

import { useState, FormEvent } from "react";
import { useLogin } from "@/lib/hooks/use-auth";
import Link from "next/link";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{
    username?: string;
    password?: string;
  }>({});

  const loginMutation = useLogin();

  const validateForm = (): boolean => {
    const newErrors: { username?: string; password?: string } = {};

    if (!username.trim()) {
      newErrors.username = "Username is required";
    }

    if (!password) {
      newErrors.password = "Password is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    loginMutation.mutate({
      username: username.trim(),
      password,
    });
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Background Orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-500/20 rounded-full blur-[120px] pointer-events-none animate-pulse-slow"></div>
      <div className="absolute bottom-1/4 right-1/4 w-[30rem] h-[30rem] bg-indigo-500/10 rounded-full blur-[120px] pointer-events-none"></div>

      <div className="max-w-md w-full mx-4 space-y-8 z-10 animate-fade-in relative">
        {/* Header */}
        <div className="text-center">
          <Link
            href="/"
            className="inline-flex items-center justify-center p-3 bg-brand-500/10 rounded-xl mb-4 border border-brand-500/20 shadow-lg shadow-brand-500/10 hover:scale-105 transition-transform"
          >
            <svg
              className="w-8 h-8 text-brand-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"
              />
            </svg>
          </Link>
          <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">
            Welcome Back
          </h1>
          <p className="text-gray-400">Sign in to VMLedger</p>
        </div>

        {/* Login Form */}
        <div className="glass-card p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Username Field */}
            <div>
              <label
                htmlFor="username"
                className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
              >
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={`input-premium ${
                  errors.username ? "border-red-500/50 bg-red-500/5" : ""
                }`}
                placeholder="Enter your username"
                disabled={loginMutation.isPending}
              />
              {errors.username && (
                <p className="mt-2 text-xs font-medium text-red-400">
                  {errors.username}
                </p>
              )}
            </div>

            {/* Password Field */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label
                  htmlFor="password"
                  className="block text-sm font-semibold text-gray-300 uppercase tracking-wide"
                >
                  Password
                </label>
              </div>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`input-premium ${
                  errors.password ? "border-red-500/50 bg-red-500/5" : ""
                }`}
                placeholder="Enter your password"
                disabled={loginMutation.isPending}
              />
              {errors.password && (
                <p className="mt-2 text-xs font-medium text-red-400">
                  {errors.password}
                </p>
              )}
            </div>

            {/* Error Message */}
            {loginMutation.isError && (
              <div className="glass-card border-red-500/30 bg-red-500/10 p-4 flex items-start gap-3">
                <svg
                  className="w-5 h-5 text-red-400 mt-0.5 shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <p className="text-sm font-medium text-red-200">
                  {loginMutation.error instanceof Error
                    ? loginMutation.error.message
                    : "Login failed. Please check your credentials."}
                </p>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loginMutation.isPending}
              className="w-full btn-primary"
            >
              {loginMutation.isPending ? (
                <span className="flex items-center justify-center">
                  <svg
                    className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  Authenticating...
                </span>
              ) : (
                "Sign In"
              )}
            </button>
          </form>

          {/* Register Link */}
          <div className="mt-8 pt-6 border-t border-white/5 text-center">
            <p className="text-gray-400 text-sm">
              Don&apos;t have an account?{" "}
              <Link
                href="/register"
                className="text-brand-400 hover:text-brand-300 font-bold transition-colors"
              >
                Create one
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
