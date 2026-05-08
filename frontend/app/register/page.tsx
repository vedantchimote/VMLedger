"use client";

import { useState, FormEvent } from "react";
import { useRegister } from "@/lib/hooks/use-auth";
import {
  isValidPassword,
  isValidEmail,
  getPasswordStrength,
} from "@/lib/validation";
import Link from "next/link";

export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<{
    username?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
  }>({});

  const registerMutation = useRegister();

  const passwordStrength = getPasswordStrength(password);

  const validateForm = (): boolean => {
    const newErrors: {
      username?: string;
      email?: string;
      password?: string;
      confirmPassword?: string;
    } = {};

    // Username validation
    if (!username.trim()) {
      newErrors.username = "Username is required";
    } else if (username.trim().length < 3) {
      newErrors.username = "Username must be at least 3 characters";
    } else if (username.trim().length > 50) {
      newErrors.username = "Username must be at most 50 characters";
    }

    // Email validation
    if (!email.trim()) {
      newErrors.email = "Email is required";
    } else if (!isValidEmail(email.trim())) {
      newErrors.email = "Please enter a valid email address";
    }

    // Password validation
    if (!password) {
      newErrors.password = "Password is required";
    } else if (!isValidPassword(password)) {
      newErrors.password = "Password does not meet complexity requirements";
    }

    // Confirm password validation
    if (!confirmPassword) {
      newErrors.confirmPassword = "Please confirm your password";
    } else if (password !== confirmPassword) {
      newErrors.confirmPassword = "Passwords do not match";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    registerMutation.mutate({
      username: username.trim(),
      email: email.trim(),
      password,
    });
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden py-12">
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
            Create Account
          </h1>
          <p className="text-gray-400">Join VMLedger today</p>
        </div>

        {/* Registration Form */}
        <div className="glass-card p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
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
                placeholder="Choose a username"
                disabled={registerMutation.isPending}
              />
              {errors.username && (
                <p className="mt-2 text-xs font-medium text-red-400">
                  {errors.username}
                </p>
              )}
            </div>

            {/* Email Field */}
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={`input-premium ${
                  errors.email ? "border-red-500/50 bg-red-500/5" : ""
                }`}
                placeholder="Enter your email"
                disabled={registerMutation.isPending}
              />
              {errors.email && (
                <p className="mt-2 text-xs font-medium text-red-400">
                  {errors.email}
                </p>
              )}
            </div>

            {/* Password Field */}
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`input-premium ${
                  errors.password ? "border-red-500/50 bg-red-500/5" : ""
                }`}
                placeholder="Create a strong password"
                disabled={registerMutation.isPending}
              />
              {errors.password && (
                <p className="mt-2 text-xs font-medium text-red-400">
                  {errors.password}
                </p>
              )}

              {/* Password Strength Indicator */}
              {password && (
                <div className="mt-3 bg-surface-900/50 rounded-lg p-3 border border-white/5">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="flex-1 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-500 ease-out ${
                          passwordStrength.strength === "strong"
                            ? "bg-brand-500 w-full shadow-[0_0_10px_rgba(45,212,191,0.5)]"
                            : passwordStrength.strength === "medium"
                              ? "bg-yellow-500 w-2/3 shadow-[0_0_10px_rgba(234,179,8,0.5)]"
                              : "bg-red-500 w-1/3 shadow-[0_0_10px_rgba(239,68,68,0.5)]"
                        }`}
                      />
                    </div>
                    <span
                      className={`text-xs font-bold uppercase tracking-wider ${
                        passwordStrength.strength === "strong"
                          ? "text-brand-400"
                          : passwordStrength.strength === "medium"
                            ? "text-yellow-400"
                            : "text-red-400"
                      }`}
                    >
                      {passwordStrength.strength}
                    </span>
                  </div>

                  {/* Password Requirements */}
                  {passwordStrength.feedback.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {passwordStrength.feedback.map((feedback, index) => (
                        <p
                          key={index}
                          className="text-[11px] font-medium text-gray-400 flex items-center gap-1.5"
                        >
                          <span className="w-1 h-1 rounded-full bg-gray-500"></span>
                          {feedback}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Confirm Password Field */}
            <div>
              <label
                htmlFor="confirmPassword"
                className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
              >
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={`input-premium ${
                  errors.confirmPassword ? "border-red-500/50 bg-red-500/5" : ""
                }`}
                placeholder="Confirm your password"
                disabled={registerMutation.isPending}
              />
              {errors.confirmPassword && (
                <p className="mt-2 text-xs font-medium text-red-400">
                  {errors.confirmPassword}
                </p>
              )}
            </div>

            {/* Password Requirements Info */}
            <div className="bg-brand-500/5 rounded-lg p-4 border border-brand-500/10 mt-6">
              <p className="text-xs text-brand-400 font-bold uppercase tracking-wider mb-2 flex items-center gap-2">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                Password Requirements
              </p>
              <ul className="text-xs text-gray-400 space-y-1.5 grid grid-cols-1 sm:grid-cols-2 gap-x-4">
                <li className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-brand-500/50"></span>
                  12+ characters
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-brand-500/50"></span>
                  Uppercase letter
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-brand-500/50"></span>
                  Lowercase letter
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-brand-500/50"></span>
                  Number
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-brand-500/50"></span>
                  Special character
                </li>
              </ul>
            </div>

            {/* Error Message */}
            {registerMutation.isError && (
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
                  {registerMutation.error instanceof Error
                    ? registerMutation.error.message
                    : "Registration failed. Please try again."}
                </p>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={registerMutation.isPending}
              className="w-full btn-primary mt-6"
            >
              {registerMutation.isPending ? (
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
                  Creating account...
                </span>
              ) : (
                "Create Account"
              )}
            </button>
          </form>

          {/* Login Link */}
          <div className="mt-8 pt-6 border-t border-white/5 text-center">
            <p className="text-gray-400 text-sm">
              Already have an account?{" "}
              <Link
                href="/login"
                className="text-brand-400 hover:text-brand-300 font-bold transition-colors"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
