"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/hooks/use-auth";
import { useCreateVM } from "@/lib/hooks/use-vms";
import {
  isValidIPAddress,
  isValidSSHPort,
  isValidHostname,
  isValidTags,
  isValidSSHKey,
} from "@/lib/validation";
import type { VMCreateRequest } from "@/types/api";

export default function NewVMPage() {
  const router = useRouter();
  const { isAuthenticated, isMounted } = useAuth();
  const createVMMutation = useCreateVM();

  // Form state
  const [formData, setFormData] = useState<VMCreateRequest>({
    ip_address: "",
    hostname: "",
    domain: "",
    ssh_port: 22,
    tags: [],
    deployment_notes: "",
    ssh_username: "root",
    ssh_private_key: "",
    ssh_password: "",
  });

  const [authMethod, setAuthMethod] = useState<"ssh_key" | "password">(
    "password",
  );
  const [tagInput, setTagInput] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (isMounted && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isMounted, router]);

  if (!isMounted || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  // Validation
  const validateField = (
    name: string,
    value: string | number | string[] | undefined,
  ): string => {
    const stringValue =
      typeof value === "number" ? String(value) : (value as string);

    switch (name) {
      case "ip_address":
        if (!stringValue) return "IP address is required";
        if (!isValidIPAddress(stringValue))
          return "Invalid IP address format (IPv4 or IPv6)";
        return "";

      case "hostname":
        if (!stringValue) return "Hostname is required";
        if (!isValidHostname(stringValue))
          return "Invalid hostname (max 255 chars, alphanumeric + hyphens)";
        return "";

      case "domain":
        if (stringValue && stringValue.length > 255)
          return "Domain must be max 255 characters";
        return "";

      case "ssh_port":
        if (!value) return "SSH port is required";
        if (!isValidSSHPort(Number(value)))
          return "SSH port must be between 1 and 65535";
        return "";

      case "ssh_username":
        if (!stringValue) return "SSH username is required";
        return "";

      case "ssh_private_key":
        if (authMethod === "ssh_key") {
          if (!stringValue) return "SSH private key is required";
          if (!isValidSSHKey(stringValue)) return "Invalid SSH key format";
        }
        return "";

      case "ssh_password":
        if (authMethod === "password" && !stringValue)
          return "SSH password is required";
        return "";

      case "deployment_notes":
        if (stringValue && stringValue.length > 50000)
          return "Deployment notes must be max 50,000 characters";
        return "";

      default:
        return "";
    }
  };

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    // Validate on change if field was touched
    if (touched[name]) {
      const error = validateField(name, value);
      setErrors((prev) => ({ ...prev, [name]: error }));
    }
  };

  const handleBlur = (
    e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    const { name, value } = e.target;
    setTouched((prev) => ({ ...prev, [name]: true }));
    const error = validateField(name, value);
    setErrors((prev) => ({ ...prev, [name]: error }));
  };

  const handleAddTag = () => {
    const trimmedTag = tagInput.trim();
    if (trimmedTag && !formData.tags?.includes(trimmedTag)) {
      const newTags = [...(formData.tags || []), trimmedTag];
      if (isValidTags(newTags)) {
        setFormData((prev) => ({ ...prev, tags: newTags }));
        setTagInput("");
        setErrors((prev) => ({ ...prev, tags: "" }));
      } else {
        setErrors((prev) => ({ ...prev, tags: "Maximum 20 tags allowed" }));
      }
    }
  };

  const handleRemoveTag = (tagToRemove: string) => {
    setFormData((prev) => ({
      ...prev,
      tags: prev.tags?.filter((tag) => tag !== tagToRemove) || [],
    }));
  };

  const handleTagInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddTag();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate all fields
    const newErrors: Record<string, string> = {};
    const fieldsToValidate = [
      "ip_address",
      "hostname",
      "domain",
      "ssh_port",
      "ssh_username",
      authMethod === "ssh_key" ? "ssh_private_key" : "ssh_password",
      "deployment_notes",
    ];

    fieldsToValidate.forEach((field) => {
      const error = validateField(
        field,
        formData[field as keyof VMCreateRequest],
      );
      if (error) newErrors[field] = error;
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      setTouched(
        fieldsToValidate.reduce(
          (acc, field) => ({ ...acc, [field]: true }),
          {},
        ),
      );
      return;
    }

    // Prepare submission data
    const submitData: VMCreateRequest = {
      ip_address: formData.ip_address,
      hostname: formData.hostname,
      domain: formData.domain || undefined,
      ssh_port: Number(formData.ssh_port),
      tags: formData.tags || [],
      deployment_notes: formData.deployment_notes || undefined,
      ssh_username: formData.ssh_username,
    };

    if (authMethod === "ssh_key") {
      submitData.ssh_private_key = formData.ssh_private_key;
    } else {
      submitData.ssh_password = formData.ssh_password;
    }

    try {
      await createVMMutation.mutateAsync(submitData);
      router.push("/dashboard");
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Failed to create VM";
      setErrors((prev) => ({
        ...prev,
        submit: errorMessage,
      }));
    }
  };

  const handleCancel = () => {
    router.push("/dashboard");
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-surface-950/60 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            <div className="flex items-center gap-3">
              <Link
                href="/dashboard"
                className="flex items-center justify-center w-10 h-10 rounded-xl bg-surface-800 border border-white/5 text-gray-400 hover:text-white hover:bg-surface-700 transition-all hover:scale-105 mr-2"
                aria-label="Back to Dashboard"
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10 19l-7-7m0 0l7-7m-7 7h18"
                  />
                </svg>
              </Link>
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 shadow-lg shadow-brand-500/20">
                <svg
                  className="w-6 h-6 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"
                  />
                </svg>
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-white">
                Register <span className="text-brand-400">Instance</span>
              </h1>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 animate-fade-in">
        <div className="glass-card p-10">
          <div className="mb-8">
            <h2 className="text-3xl font-bold text-white mb-2 tracking-tight">
              Register New Virtual Machine
            </h2>
            <p className="text-gray-400">
              Add a new VM to your infrastructure ledger for centralized
              monitoring and management.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* IP Address */}
              <div>
                <label
                  htmlFor="ip_address"
                  className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
                >
                  IP Address <span className="text-brand-400">*</span>
                </label>
                <input
                  type="text"
                  id="ip_address"
                  name="ip_address"
                  value={formData.ip_address}
                  onChange={handleInputChange}
                  onBlur={handleBlur}
                  className={`input-premium ${
                    errors.ip_address && touched.ip_address
                      ? "border-red-500/50 bg-red-500/5"
                      : ""
                  }`}
                  placeholder="192.168.1.100 or 2001:db8::1"
                />
                {errors.ip_address && touched.ip_address && (
                  <p className="mt-2 text-xs font-medium text-red-400">
                    {errors.ip_address}
                  </p>
                )}
              </div>

              {/* Hostname */}
              <div>
                <label
                  htmlFor="hostname"
                  className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
                >
                  Hostname <span className="text-brand-400">*</span>
                </label>
                <input
                  type="text"
                  id="hostname"
                  name="hostname"
                  value={formData.hostname}
                  onChange={handleInputChange}
                  onBlur={handleBlur}
                  className={`input-premium ${
                    errors.hostname && touched.hostname
                      ? "border-red-500/50 bg-red-500/5"
                      : ""
                  }`}
                  placeholder="web-server-01"
                />
                {errors.hostname && touched.hostname && (
                  <p className="mt-2 text-xs font-medium text-red-400">
                    {errors.hostname}
                  </p>
                )}
              </div>

              {/* Domain */}
              <div>
                <label
                  htmlFor="domain"
                  className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
                >
                  Domain{" "}
                  <span className="text-gray-500 normal-case font-normal">
                    (Optional)
                  </span>
                </label>
                <input
                  type="text"
                  id="domain"
                  name="domain"
                  value={formData.domain}
                  onChange={handleInputChange}
                  onBlur={handleBlur}
                  className={`input-premium ${
                    errors.domain && touched.domain
                      ? "border-red-500/50 bg-red-500/5"
                      : ""
                  }`}
                  placeholder="example.com"
                />
                {errors.domain && touched.domain && (
                  <p className="mt-2 text-xs font-medium text-red-400">
                    {errors.domain}
                  </p>
                )}
              </div>

              {/* SSH Port */}
              <div>
                <label
                  htmlFor="ssh_port"
                  className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
                >
                  SSH Port <span className="text-brand-400">*</span>
                </label>
                <input
                  type="number"
                  id="ssh_port"
                  name="ssh_port"
                  value={formData.ssh_port}
                  onChange={handleInputChange}
                  onBlur={handleBlur}
                  min="1"
                  max="65535"
                  className={`input-premium ${
                    errors.ssh_port && touched.ssh_port
                      ? "border-red-500/50 bg-red-500/5"
                      : ""
                  }`}
                  placeholder="22"
                />
                {errors.ssh_port && touched.ssh_port && (
                  <p className="mt-2 text-xs font-medium text-red-400">
                    {errors.ssh_port}
                  </p>
                )}
              </div>

              {/* SSH Username */}
              <div>
                <label
                  htmlFor="ssh_username"
                  className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
                >
                  SSH Username <span className="text-brand-400">*</span>
                </label>
                <input
                  type="text"
                  id="ssh_username"
                  name="ssh_username"
                  value={formData.ssh_username}
                  onChange={handleInputChange}
                  onBlur={handleBlur}
                  className={`input-premium ${
                    errors.ssh_username && touched.ssh_username
                      ? "border-red-500/50 bg-red-500/5"
                      : ""
                  }`}
                  placeholder="root"
                />
                {errors.ssh_username && touched.ssh_username && (
                  <p className="mt-2 text-xs font-medium text-red-400">
                    {errors.ssh_username}
                  </p>
                )}
              </div>
            </div>

            <div className="border-t border-white/5 pt-6">
              <h3 className="text-lg font-bold text-white mb-4">
                Authentication
              </h3>
              {/* Authentication Method */}
              <div className="mb-6">
                <div className="flex gap-4 p-1 bg-surface-900/50 border border-white/5 rounded-xl w-max">
                  <label
                    className={`cursor-pointer px-6 py-2 rounded-lg text-sm font-bold uppercase tracking-wider transition-all ${authMethod === "password" ? "bg-brand-500/20 text-brand-300 border border-brand-500/30 shadow-inner" : "text-gray-400 hover:text-gray-200 border border-transparent"}`}
                  >
                    <input
                      type="radio"
                      name="auth_method"
                      value="password"
                      checked={authMethod === "password"}
                      onChange={() => setAuthMethod("password")}
                      className="hidden"
                    />
                    Password
                  </label>
                  <label
                    className={`cursor-pointer px-6 py-2 rounded-lg text-sm font-bold uppercase tracking-wider transition-all ${authMethod === "ssh_key" ? "bg-brand-500/20 text-brand-300 border border-brand-500/30 shadow-inner" : "text-gray-400 hover:text-gray-200 border border-transparent"}`}
                  >
                    <input
                      type="radio"
                      name="auth_method"
                      value="ssh_key"
                      checked={authMethod === "ssh_key"}
                      onChange={() => setAuthMethod("ssh_key")}
                      className="hidden"
                    />
                    SSH Key
                  </label>
                </div>
              </div>

              {/* SSH Password (conditional) */}
              <div
                className={`transition-all duration-300 ${authMethod === "password" ? "opacity-100 max-h-[100px]" : "opacity-0 max-h-0 overflow-hidden"}`}
              >
                <label
                  htmlFor="ssh_password"
                  className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
                >
                  SSH Password <span className="text-brand-400">*</span>
                </label>
                <input
                  type="password"
                  id="ssh_password"
                  name="ssh_password"
                  value={formData.ssh_password}
                  onChange={handleInputChange}
                  onBlur={handleBlur}
                  className={`input-premium ${
                    errors.ssh_password && touched.ssh_password
                      ? "border-red-500/50 bg-red-500/5"
                      : ""
                  }`}
                  placeholder="Enter SSH password"
                />
                {errors.ssh_password && touched.ssh_password && (
                  <p className="mt-2 text-xs font-medium text-red-400">
                    {errors.ssh_password}
                  </p>
                )}
              </div>

              {/* SSH Private Key (conditional) */}
              <div
                className={`transition-all duration-300 ${authMethod === "ssh_key" ? "opacity-100 max-h-[500px]" : "opacity-0 max-h-0 overflow-hidden"}`}
              >
                <label
                  htmlFor="ssh_private_key"
                  className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
                >
                  SSH Private Key <span className="text-brand-400">*</span>
                </label>
                <textarea
                  id="ssh_private_key"
                  name="ssh_private_key"
                  value={formData.ssh_private_key}
                  onChange={handleInputChange}
                  onBlur={handleBlur}
                  rows={8}
                  className={`input-premium font-mono text-xs leading-relaxed resize-y ${
                    errors.ssh_private_key && touched.ssh_private_key
                      ? "border-red-500/50 bg-red-500/5"
                      : ""
                  }`}
                  placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;...&#10;-----END RSA PRIVATE KEY-----"
                />
                {errors.ssh_private_key && touched.ssh_private_key && (
                  <p className="mt-2 text-xs font-medium text-red-400">
                    {errors.ssh_private_key}
                  </p>
                )}
              </div>
            </div>

            <div className="border-t border-white/5 pt-6">
              <h3 className="text-lg font-bold text-white mb-4">
                Metadata & Configuration
              </h3>
              {/* Tags */}
              <div className="mb-6">
                <label
                  htmlFor="tag_input"
                  className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
                >
                  Tags{" "}
                  <span className="text-gray-500 normal-case font-normal">
                    (Max 20)
                  </span>
                </label>
                <div className="flex gap-3 mb-3">
                  <div className="relative flex-1">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <span className="text-gray-500 font-bold">#</span>
                    </div>
                    <input
                      type="text"
                      id="tag_input"
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyDown={handleTagInputKeyDown}
                      className="input-premium pl-8"
                      placeholder="database, production, us-east..."
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleAddTag}
                    className="btn-secondary"
                  >
                    Add Tag
                  </button>
                </div>
                {errors.tags && (
                  <p className="mt-2 text-xs font-medium text-red-400 mb-2">
                    {errors.tags}
                  </p>
                )}
                <div className="flex flex-wrap gap-2 min-h-[32px]">
                  {formData.tags?.map((tag, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center px-3 py-1 bg-surface-800 border border-white/10 rounded-lg text-gray-300 text-xs font-bold uppercase tracking-wider group hover:border-red-500/50 transition-colors"
                    >
                      {tag}
                      <button
                        type="button"
                        onClick={() => handleRemoveTag(tag)}
                        className="ml-2 text-gray-500 group-hover:text-red-400 transition-colors focus:outline-none"
                      >
                        <svg
                          className="w-3 h-3"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={3}
                            d="M6 18L18 6M6 6l12 12"
                          />
                        </svg>
                      </button>
                    </span>
                  ))}
                  {(!formData.tags || formData.tags.length === 0) && (
                    <span className="text-sm text-gray-500 italic flex items-center h-8">
                      No tags added
                    </span>
                  )}
                </div>
              </div>

              {/* Deployment Notes */}
              <div>
                <label
                  htmlFor="deployment_notes"
                  className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
                >
                  Deployment Notes{" "}
                  <span className="text-gray-500 normal-case font-normal">
                    (Markdown supported)
                  </span>
                </label>
                <textarea
                  id="deployment_notes"
                  name="deployment_notes"
                  value={formData.deployment_notes}
                  onChange={handleInputChange}
                  onBlur={handleBlur}
                  rows={5}
                  className={`input-premium resize-y ${
                    errors.deployment_notes && touched.deployment_notes
                      ? "border-red-500/50 bg-red-500/5"
                      : ""
                  }`}
                  placeholder="# Infrastructure Details&#10;- Installed Nginx 1.20&#10;- Configured firewall rules"
                />
                {errors.deployment_notes && touched.deployment_notes && (
                  <p className="mt-2 text-xs font-medium text-red-400">
                    {errors.deployment_notes}
                  </p>
                )}
              </div>
            </div>

            {/* Submit Error */}
            {errors.submit && (
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
                <p className="text-red-200 text-sm font-medium">
                  {errors.submit}
                </p>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-4 pt-6 mt-8 border-t border-white/5">
              <button
                type="button"
                onClick={handleCancel}
                disabled={createVMMutation.isPending}
                className="flex-1 btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createVMMutation.isPending}
                className="flex-[2] btn-primary"
              >
                {createVMMutation.isPending ? (
                  <>
                    <svg
                      className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
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
                    Provisioning Instance...
                  </>
                ) : (
                  "Deploy Virtual Machine"
                )}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
