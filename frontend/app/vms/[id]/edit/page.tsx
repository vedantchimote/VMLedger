"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "@/lib/hooks/use-auth";
import { useVM, useUpdateVM, useDeleteVM } from "@/lib/hooks/use-vms";
import {
  isValidIPAddress,
  isValidSSHPort,
  isValidHostname,
  isValidTags,
  isValidSSHKey,
} from "@/lib/validation";
import type { VMUpdateRequest } from "@/types/api";

export default function EditVMPage() {
  const router = useRouter();
  const params = useParams();
  const vmId = Number(params.id);

  const { isAuthenticated, isMounted } = useAuth();
  const { data: vm, isLoading: isLoadingVM } = useVM(vmId);
  const updateVMMutation = useUpdateVM();
  const deleteVMMutation = useDeleteVM();

  // Form state
  const [formData, setFormData] = useState<VMUpdateRequest>({
    ip_address: "",
    hostname: "",
    domain: "",
    ssh_port: 22,
    tags: [],
    deployment_notes: "",
    ssh_username: "root",
    ssh_private_key: "",
    ssh_password: "",
    ping_interval_minutes: 5,
    dns_interval_hours: 6,
  });

  const [authMethod, setAuthMethod] = useState<"ssh_key" | "password" | "none">(
    "none",
  );
  const [tagInput, setTagInput] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Deployment notes editor state
  const [notesTab, setNotesTab] = useState<"edit" | "preview">("edit");
  const [autoSaveStatus, setAutoSaveStatus] = useState<
    "idle" | "saving" | "saved" | "error"
  >("idle");
  const autoSaveTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastSavedNotesRef = useRef<string>("");

  // Populate form with existing VM data
  useEffect(() => {
    if (vm) {
      setFormData({
        ip_address: vm.ip_address,
        hostname: vm.hostname,
        domain: vm.domain || "",
        ssh_port: vm.ssh_port,
        tags: vm.tags || [],
        deployment_notes: vm.deployment_notes || "",
        ssh_username: "root", // Default, will be updated if needed
        ping_interval_minutes: vm.ping_interval_minutes || 5,
        dns_interval_hours: vm.dns_interval_hours || 6,
      });
      // Initialize last saved notes
      lastSavedNotesRef.current = vm.deployment_notes || "";
    }
  }, [vm]);

  useEffect(() => {
    if (isMounted && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isMounted, router]);

  // Auto-save deployment notes
  const autoSaveNotes = useCallback(
    async (notes: string) => {
      if (notes === lastSavedNotesRef.current) {
        return; // No changes, skip save
      }

      setAutoSaveStatus("saving");

      try {
        await updateVMMutation.mutateAsync({
          vmId,
          vmData: { deployment_notes: notes },
        });
        lastSavedNotesRef.current = notes;
        setAutoSaveStatus("saved");

        // Reset to idle after 2 seconds
        setTimeout(() => {
          setAutoSaveStatus("idle");
        }, 2000);
      } catch (error) {
        console.error("Auto-save failed:", error);
        setAutoSaveStatus("error");

        // Reset to idle after 3 seconds
        setTimeout(() => {
          setAutoSaveStatus("idle");
        }, 3000);
      }
    },
    [vmId, updateVMMutation],
  );

  // Debounced auto-save effect
  useEffect(() => {
    const notes = formData.deployment_notes || "";

    // Clear existing timer
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }

    // Only auto-save if notes have changed and are different from last saved
    if (notes !== lastSavedNotesRef.current) {
      // Set timer for 2 seconds after user stops typing
      autoSaveTimerRef.current = setTimeout(() => {
        autoSaveNotes(notes);
      }, 2000);
    }

    // Cleanup on unmount
    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
    };
  }, [formData.deployment_notes, autoSaveNotes]);

  if (!isMounted || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  if (isLoadingVM) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-white">Loading VM data...</div>
      </div>
    );
  }

  if (!vm) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-red-400">VM not found</div>
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
        if (authMethod !== "none" && !stringValue)
          return "SSH username is required";
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

      case "ping_interval_minutes":
        if (Number(value) < 1) return "Ping interval must be at least 1 minute";
        return "";

      case "dns_interval_hours":
        if (Number(value) < 1) return "DNS interval must be at least 1 hour";
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
      "deployment_notes",
    ];

    if (authMethod !== "none") {
      fieldsToValidate.push("ssh_username");
      if (authMethod === "ssh_key") {
        fieldsToValidate.push("ssh_private_key");
      } else if (authMethod === "password") {
        fieldsToValidate.push("ssh_password");
      }
    }

    fieldsToValidate.forEach((field) => {
      const error = validateField(
        field,
        formData[field as keyof VMUpdateRequest],
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
    const submitData: VMUpdateRequest = {
      ip_address: formData.ip_address,
      hostname: formData.hostname,
      domain: formData.domain || undefined,
      ssh_port: Number(formData.ssh_port),
      tags: formData.tags || [],
      deployment_notes: formData.deployment_notes || undefined,
      ping_interval_minutes: Number(formData.ping_interval_minutes),
      dns_interval_hours: Number(formData.dns_interval_hours),
    };

    // Only include credentials if updating them
    if (authMethod === "ssh_key") {
      submitData.ssh_username = formData.ssh_username;
      submitData.ssh_private_key = formData.ssh_private_key;
    } else if (authMethod === "password") {
      submitData.ssh_username = formData.ssh_username;
      submitData.ssh_password = formData.ssh_password;
    }

    try {
      await updateVMMutation.mutateAsync({ vmId, vmData: submitData });
      router.push("/dashboard");
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Failed to update VM";
      setErrors((prev) => ({
        ...prev,
        submit: errorMessage,
      }));
    }
  };

  const handleDelete = async () => {
    try {
      await deleteVMMutation.mutateAsync(vmId);
      router.push("/dashboard");
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Failed to delete VM";
      setErrors((prev) => ({
        ...prev,
        submit: errorMessage,
      }));
      setShowDeleteConfirm(false);
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
                href={`/vms/${vmId}`}
                className="flex items-center justify-center w-10 h-10 rounded-xl bg-surface-800 border border-white/5 text-gray-400 hover:text-white hover:bg-surface-700 transition-all hover:scale-105 mr-2"
                aria-label="Back to VM Details"
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
              <h1 className="text-2xl font-bold tracking-tight text-white">
                Edit <span className="text-brand-400">{vm.hostname}</span>
              </h1>
            </div>
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-lg transition-colors duration-200 text-sm font-bold flex items-center shadow-inner"
            >
              <svg
                className="w-4 h-4 mr-2"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
              Delete Instance
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 animate-fade-in">
        <div className="glass-card p-10">
          <form onSubmit={handleSubmit} className="space-y-8">
            {/* Basic Information */}
            <div>
              <h3 className="text-lg font-bold text-white mb-6 border-b border-white/5 pb-2">
                Instance Details
              </h3>
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
              </div>

              {/* Interval Settings */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                {/* Ping Interval */}
                <div>
                  <label
                    htmlFor="ping_interval_minutes"
                    className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
                  >
                    Ping Check Interval (Minutes) <span className="text-brand-400">*</span>
                  </label>
                  <input
                    type="number"
                    id="ping_interval_minutes"
                    name="ping_interval_minutes"
                    value={formData.ping_interval_minutes}
                    onChange={handleInputChange}
                    onBlur={handleBlur}
                    min="1"
                    className={`input-premium ${
                      errors.ping_interval_minutes && touched.ping_interval_minutes
                        ? "border-red-500/50 bg-red-500/5"
                        : ""
                    }`}
                    placeholder="5"
                  />
                  {errors.ping_interval_minutes && touched.ping_interval_minutes && (
                    <p className="mt-2 text-xs font-medium text-red-400">
                      {errors.ping_interval_minutes}
                    </p>
                  )}
                </div>

                {/* DNS Interval */}
                <div>
                  <label
                    htmlFor="dns_interval_hours"
                    className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide"
                  >
                    DNS Check Interval (Hours) <span className="text-brand-400">*</span>
                  </label>
                  <input
                    type="number"
                    id="dns_interval_hours"
                    name="dns_interval_hours"
                    value={formData.dns_interval_hours}
                    onChange={handleInputChange}
                    onBlur={handleBlur}
                    min="1"
                    className={`input-premium ${
                      errors.dns_interval_hours && touched.dns_interval_hours
                        ? "border-red-500/50 bg-red-500/5"
                        : ""
                    }`}
                    placeholder="6"
                  />
                  {errors.dns_interval_hours && touched.dns_interval_hours && (
                    <p className="mt-2 text-xs font-medium text-red-400">
                      {errors.dns_interval_hours}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Update Credentials Section */}
            <div className="pt-2">
              <h3 className="text-lg font-bold text-white mb-6 border-b border-white/5 pb-2 flex justify-between items-center">
                Authentication Update
                <span className="text-xs font-normal text-gray-500 bg-surface-800 px-2 py-1 rounded">
                  Optional
                </span>
              </h3>

              {/* Authentication Method */}
              <div className="mb-6">
                <div className="flex gap-4 p-1 bg-surface-900/50 border border-white/5 rounded-xl w-max">
                  <label
                    className={`cursor-pointer px-6 py-2 rounded-lg text-sm font-bold uppercase tracking-wider transition-all ${authMethod === "none" ? "bg-surface-700 text-white shadow-inner" : "text-gray-400 hover:text-gray-200 border border-transparent"}`}
                  >
                    <input
                      type="radio"
                      name="auth_method"
                      value="none"
                      checked={authMethod === "none"}
                      onChange={() => setAuthMethod("none")}
                      className="hidden"
                    />
                    Keep Existing
                  </label>
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
                    New Password
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
                    New SSH Key
                  </label>
                </div>
              </div>

              <div
                className={`transition-all duration-300 space-y-6 ${authMethod !== "none" ? "opacity-100 max-h-[800px] mt-6" : "opacity-0 max-h-0 overflow-hidden"}`}
              >
                {/* SSH Username (conditional) */}
                {authMethod !== "none" && (
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
                      className={`input-premium max-w-md ${
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
                )}

                {/* SSH Password (conditional) */}
                {authMethod === "password" && (
                  <div>
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
                      className={`input-premium max-w-md ${
                        errors.ssh_password && touched.ssh_password
                          ? "border-red-500/50 bg-red-500/5"
                          : ""
                      }`}
                      placeholder="Enter new SSH password"
                    />
                    {errors.ssh_password && touched.ssh_password && (
                      <p className="mt-2 text-xs font-medium text-red-400">
                        {errors.ssh_password}
                      </p>
                    )}
                  </div>
                )}

                {/* SSH Private Key (conditional) */}
                {authMethod === "ssh_key" && (
                  <div>
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
                )}
              </div>
            </div>

            {/* Metadata & Configuration Section */}
            <div className="pt-2">
              <h3 className="text-lg font-bold text-white mb-6 border-b border-white/5 pb-2">
                Metadata & Configuration
              </h3>

              {/* Tags */}
              <div className="mb-8">
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
                <div className="flex items-center justify-between mb-4">
                  <label className="block text-sm font-semibold text-gray-300 uppercase tracking-wide">
                    Deployment Notes{" "}
                    <span className="text-gray-500 normal-case font-normal">
                      (Markdown supported)
                    </span>
                  </label>
                  <div className="flex items-center gap-4">
                    {/* Auto-save status indicator */}
                    <div className="text-xs font-bold uppercase tracking-wider">
                      {autoSaveStatus === "saving" && (
                        <span className="text-brand-400 flex items-center gap-1.5 animate-pulse">
                          <svg
                            className="animate-spin h-3.5 w-3.5"
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
                          Saving...
                        </span>
                      )}
                      {autoSaveStatus === "saved" && (
                        <span className="text-green-400 flex items-center gap-1.5">
                          <svg
                            className="h-3.5 w-3.5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M5 13l4 4L19 7"
                            />
                          </svg>
                          Saved
                        </span>
                      )}
                      {autoSaveStatus === "error" && (
                        <span className="text-red-400 flex items-center gap-1.5">
                          <svg
                            className="h-3.5 w-3.5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M6 18L18 6M6 6l12 12"
                            />
                          </svg>
                          Save failed
                        </span>
                      )}
                    </div>
                    {/* Character counter */}
                    <div
                      className={`text-xs font-mono font-medium ${
                        (formData.deployment_notes?.length || 0) >= 49000
                          ? "text-red-400"
                          : (formData.deployment_notes?.length || 0) >= 45000
                            ? "text-yellow-400"
                            : "text-gray-500"
                      }`}
                    >
                      {formData.deployment_notes?.length || 0} / 50k
                    </div>
                  </div>
                </div>

                <div className="glass-panel overflow-hidden border-white/5">
                  {/* Tab buttons */}
                  <div className="flex bg-surface-900/50 border-b border-white/5">
                    <button
                      type="button"
                      onClick={() => setNotesTab("edit")}
                      className={`px-6 py-3 text-sm font-bold uppercase tracking-wider transition-all ${
                        notesTab === "edit"
                          ? "border-b-2 border-brand-400 text-brand-400 bg-brand-500/5"
                          : "border-b-2 border-transparent text-gray-400 hover:text-white hover:bg-white/5"
                      }`}
                    >
                      Write
                    </button>
                    <button
                      type="button"
                      onClick={() => setNotesTab("preview")}
                      className={`px-6 py-3 text-sm font-bold uppercase tracking-wider transition-all ${
                        notesTab === "preview"
                          ? "border-b-2 border-brand-400 text-brand-400 bg-brand-500/5"
                          : "border-b-2 border-transparent text-gray-400 hover:text-white hover:bg-white/5"
                      }`}
                    >
                      Preview
                    </button>
                  </div>

                  {/* Tab content */}
                  <div className="p-0">
                    {notesTab === "edit" ? (
                      <textarea
                        id="deployment_notes"
                        name="deployment_notes"
                        value={formData.deployment_notes}
                        onChange={handleInputChange}
                        onBlur={handleBlur}
                        rows={12}
                        className={`w-full p-4 bg-transparent border-0 text-white placeholder-gray-500 focus:outline-none focus:ring-0 font-mono text-sm leading-relaxed resize-y ${
                          errors.deployment_notes && touched.deployment_notes
                            ? "bg-red-500/5"
                            : ""
                        }`}
                        placeholder="# Software Installed&#10;- Nginx 1.20&#10;- Node.js 18.x&#10;&#10;## Configuration&#10;- SSL enabled&#10;- Port 443"
                      />
                    ) : (
                      <div className="min-h-[300px] p-6 overflow-auto">
                        {formData.deployment_notes &&
                        formData.deployment_notes.trim() !== "" ? (
                          <div className="prose prose-invert prose-sm max-w-none prose-pre:bg-surface-800 prose-pre:border prose-pre:border-white/5">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {formData.deployment_notes}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          <div className="flex items-center justify-center h-[300px] text-gray-500 text-sm italic">
                            Nothing to preview
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

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
                disabled={updateVMMutation.isPending}
                className="flex-1 btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={updateVMMutation.isPending}
                className="flex-[2] btn-primary"
              >
                {updateVMMutation.isPending ? (
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
                    Saving Changes...
                  </>
                ) : (
                  "Save Configuration"
                )}
              </button>
            </div>
          </form>
        </div>
      </main>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-surface-950/80 backdrop-blur-sm flex items-center justify-center z-[100] p-4 animate-fade-in">
          <div className="glass-card max-w-md w-full border-red-500/20 shadow-2xl shadow-red-500/10 transform transition-all scale-100">
            <div className="p-6">
              <div className="flex items-center gap-4 mb-4">
                <div className="p-3 bg-red-500/10 rounded-full text-red-400">
                  <svg
                    className="w-6 h-6"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-white tracking-tight">
                  Confirm Deletion
                </h3>
              </div>

              <div className="text-gray-300 mb-6 space-y-4">
                <p>
                  Are you sure you want to delete{" "}
                  <strong className="text-white font-mono bg-white/5 px-1.5 py-0.5 rounded">
                    {vm.hostname}
                  </strong>
                  ?
                </p>
                <div className="bg-red-500/5 border border-red-500/20 p-4 rounded-xl text-sm text-red-200">
                  <strong className="block text-red-400 mb-1">
                    Warning: Irreversible Action
                  </strong>
                  This will permanently delete the VM, all associated
                  credentials, monitoring data, and deployment notes. This
                  action cannot be undone.
                </div>
              </div>

              <div className="flex gap-4">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={deleteVMMutation.isPending}
                  className="flex-1 btn-secondary"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleteVMMutation.isPending}
                  className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:bg-red-900 disabled:text-red-400 text-white rounded-lg transition-colors duration-200 font-bold shadow-lg shadow-red-600/20"
                >
                  {deleteVMMutation.isPending
                    ? "Deleting..."
                    : "Delete Instance"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
