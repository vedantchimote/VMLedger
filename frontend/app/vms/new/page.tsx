'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/hooks/use-auth';
import { useCreateVM } from '@/lib/hooks/use-vms';
import {
  isValidIPAddress,
  isValidSSHPort,
  isValidHostname,
  isValidTags,
  isValidSSHKey,
} from '@/lib/validation';
import type { VMCreateRequest } from '@/types/api';

export default function NewVMPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const createVMMutation = useCreateVM();

  // Form state
  const [formData, setFormData] = useState<VMCreateRequest>({
    ip_address: '',
    hostname: '',
    domain: '',
    ssh_port: 22,
    tags: [],
    deployment_notes: '',
    ssh_username: 'root',
    ssh_private_key: '',
    ssh_password: '',
  });

  const [authMethod, setAuthMethod] = useState<'ssh_key' | 'password'>('ssh_key');
  const [tagInput, setTagInput] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  // Validation
  const validateField = (name: string, value: string | number | string[] | undefined): string => {
    const stringValue = typeof value === 'number' ? String(value) : (value as string);
    
    switch (name) {
      case 'ip_address':
        if (!stringValue) return 'IP address is required';
        if (!isValidIPAddress(stringValue)) return 'Invalid IP address format (IPv4 or IPv6)';
        return '';
      
      case 'hostname':
        if (!stringValue) return 'Hostname is required';
        if (!isValidHostname(stringValue)) return 'Invalid hostname (max 255 chars, alphanumeric + hyphens)';
        return '';
      
      case 'domain':
        if (stringValue && stringValue.length > 255) return 'Domain must be max 255 characters';
        return '';
      
      case 'ssh_port':
        if (!value) return 'SSH port is required';
        if (!isValidSSHPort(Number(value))) return 'SSH port must be between 1 and 65535';
        return '';
      
      case 'ssh_username':
        if (!stringValue) return 'SSH username is required';
        return '';
      
      case 'ssh_private_key':
        if (authMethod === 'ssh_key') {
          if (!stringValue) return 'SSH private key is required';
          if (!isValidSSHKey(stringValue)) return 'Invalid SSH key format';
        }
        return '';
      
      case 'ssh_password':
        if (authMethod === 'password' && !stringValue) return 'SSH password is required';
        return '';
      
      case 'deployment_notes':
        if (stringValue && stringValue.length > 50000) return 'Deployment notes must be max 50,000 characters';
        return '';
      
      default:
        return '';
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    
    // Validate on change if field was touched
    if (touched[name]) {
      const error = validateField(name, value);
      setErrors(prev => ({ ...prev, [name]: error }));
    }
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setTouched(prev => ({ ...prev, [name]: true }));
    const error = validateField(name, value);
    setErrors(prev => ({ ...prev, [name]: error }));
  };

  const handleAddTag = () => {
    const trimmedTag = tagInput.trim();
    if (trimmedTag && !formData.tags?.includes(trimmedTag)) {
      const newTags = [...(formData.tags || []), trimmedTag];
      if (isValidTags(newTags)) {
        setFormData(prev => ({ ...prev, tags: newTags }));
        setTagInput('');
        setErrors(prev => ({ ...prev, tags: '' }));
      } else {
        setErrors(prev => ({ ...prev, tags: 'Maximum 20 tags allowed' }));
      }
    }
  };

  const handleRemoveTag = (tagToRemove: string) => {
    setFormData(prev => ({
      ...prev,
      tags: prev.tags?.filter(tag => tag !== tagToRemove) || [],
    }));
  };

  const handleTagInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddTag();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate all fields
    const newErrors: Record<string, string> = {};
    const fieldsToValidate = [
      'ip_address',
      'hostname',
      'domain',
      'ssh_port',
      'ssh_username',
      authMethod === 'ssh_key' ? 'ssh_private_key' : 'ssh_password',
      'deployment_notes',
    ];

    fieldsToValidate.forEach(field => {
      const error = validateField(field, formData[field as keyof VMCreateRequest]);
      if (error) newErrors[field] = error;
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      setTouched(
        fieldsToValidate.reduce((acc, field) => ({ ...acc, [field]: true }), {})
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

    if (authMethod === 'ssh_key') {
      submitData.ssh_private_key = formData.ssh_private_key;
    } else {
      submitData.ssh_password = formData.ssh_password;
    }

    try {
      await createVMMutation.mutateAsync(submitData);
      router.push('/dashboard');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to create VM';
      setErrors(prev => ({
        ...prev,
        submit: errorMessage,
      }));
    }
  };

  const handleCancel = () => {
    router.push('/dashboard');
  };

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-white">VMLedger</h1>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-gray-800 rounded-lg shadow-xl p-8 border border-gray-700">
          <h2 className="text-3xl font-bold text-white mb-6">Register New VM</h2>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* IP Address */}
            <div>
              <label htmlFor="ip_address" className="block text-sm font-medium text-gray-300 mb-2">
                IP Address *
              </label>
              <input
                type="text"
                id="ip_address"
                name="ip_address"
                value={formData.ip_address}
                onChange={handleInputChange}
                onBlur={handleBlur}
                className={`w-full px-4 py-2 bg-gray-700 border ${
                  errors.ip_address && touched.ip_address ? 'border-red-500' : 'border-gray-600'
                } rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                placeholder="192.168.1.100 or 2001:db8::1"
              />
              {errors.ip_address && touched.ip_address && (
                <p className="mt-1 text-sm text-red-400">{errors.ip_address}</p>
              )}
            </div>

            {/* Hostname */}
            <div>
              <label htmlFor="hostname" className="block text-sm font-medium text-gray-300 mb-2">
                Hostname *
              </label>
              <input
                type="text"
                id="hostname"
                name="hostname"
                value={formData.hostname}
                onChange={handleInputChange}
                onBlur={handleBlur}
                className={`w-full px-4 py-2 bg-gray-700 border ${
                  errors.hostname && touched.hostname ? 'border-red-500' : 'border-gray-600'
                } rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                placeholder="web-server-01"
              />
              {errors.hostname && touched.hostname && (
                <p className="mt-1 text-sm text-red-400">{errors.hostname}</p>
              )}
            </div>

            {/* Domain */}
            <div>
              <label htmlFor="domain" className="block text-sm font-medium text-gray-300 mb-2">
                Domain (optional)
              </label>
              <input
                type="text"
                id="domain"
                name="domain"
                value={formData.domain}
                onChange={handleInputChange}
                onBlur={handleBlur}
                className={`w-full px-4 py-2 bg-gray-700 border ${
                  errors.domain && touched.domain ? 'border-red-500' : 'border-gray-600'
                } rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                placeholder="example.com"
              />
              {errors.domain && touched.domain && (
                <p className="mt-1 text-sm text-red-400">{errors.domain}</p>
              )}
            </div>

            {/* SSH Port */}
            <div>
              <label htmlFor="ssh_port" className="block text-sm font-medium text-gray-300 mb-2">
                SSH Port *
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
                className={`w-full px-4 py-2 bg-gray-700 border ${
                  errors.ssh_port && touched.ssh_port ? 'border-red-500' : 'border-gray-600'
                } rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                placeholder="22"
              />
              {errors.ssh_port && touched.ssh_port && (
                <p className="mt-1 text-sm text-red-400">{errors.ssh_port}</p>
              )}
            </div>

            {/* SSH Username */}
            <div>
              <label htmlFor="ssh_username" className="block text-sm font-medium text-gray-300 mb-2">
                SSH Username *
              </label>
              <input
                type="text"
                id="ssh_username"
                name="ssh_username"
                value={formData.ssh_username}
                onChange={handleInputChange}
                onBlur={handleBlur}
                className={`w-full px-4 py-2 bg-gray-700 border ${
                  errors.ssh_username && touched.ssh_username ? 'border-red-500' : 'border-gray-600'
                } rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                placeholder="root"
              />
              {errors.ssh_username && touched.ssh_username && (
                <p className="mt-1 text-sm text-red-400">{errors.ssh_username}</p>
              )}
            </div>

            {/* Authentication Method */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Authentication Method *
              </label>
              <div className="flex gap-4">
                <label className="flex items-center">
                  <input
                    type="radio"
                    name="auth_method"
                    value="ssh_key"
                    checked={authMethod === 'ssh_key'}
                    onChange={() => setAuthMethod('ssh_key')}
                    className="mr-2"
                  />
                  <span className="text-gray-300">SSH Key</span>
                </label>
                <label className="flex items-center">
                  <input
                    type="radio"
                    name="auth_method"
                    value="password"
                    checked={authMethod === 'password'}
                    onChange={() => setAuthMethod('password')}
                    className="mr-2"
                  />
                  <span className="text-gray-300">Password</span>
                </label>
              </div>
            </div>

            {/* SSH Private Key (conditional) */}
            {authMethod === 'ssh_key' && (
              <div>
                <label htmlFor="ssh_private_key" className="block text-sm font-medium text-gray-300 mb-2">
                  SSH Private Key *
                </label>
                <textarea
                  id="ssh_private_key"
                  name="ssh_private_key"
                  value={formData.ssh_private_key}
                  onChange={handleInputChange}
                  onBlur={handleBlur}
                  rows={10}
                  className={`w-full px-4 py-2 bg-gray-700 border ${
                    errors.ssh_private_key && touched.ssh_private_key ? 'border-red-500' : 'border-gray-600'
                  } rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm`}
                  placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;...&#10;-----END RSA PRIVATE KEY-----"
                />
                {errors.ssh_private_key && touched.ssh_private_key && (
                  <p className="mt-1 text-sm text-red-400">{errors.ssh_private_key}</p>
                )}
              </div>
            )}

            {/* SSH Password (conditional) */}
            {authMethod === 'password' && (
              <div>
                <label htmlFor="ssh_password" className="block text-sm font-medium text-gray-300 mb-2">
                  SSH Password *
                </label>
                <input
                  type="password"
                  id="ssh_password"
                  name="ssh_password"
                  value={formData.ssh_password}
                  onChange={handleInputChange}
                  onBlur={handleBlur}
                  className={`w-full px-4 py-2 bg-gray-700 border ${
                    errors.ssh_password && touched.ssh_password ? 'border-red-500' : 'border-gray-600'
                  } rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                  placeholder="Enter SSH password"
                />
                {errors.ssh_password && touched.ssh_password && (
                  <p className="mt-1 text-sm text-red-400">{errors.ssh_password}</p>
                )}
              </div>
            )}

            {/* Tags */}
            <div>
              <label htmlFor="tag_input" className="block text-sm font-medium text-gray-300 mb-2">
                Tags (max 20)
              </label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  id="tag_input"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={handleTagInputKeyDown}
                  className="flex-1 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Enter tag and press Enter"
                />
                <button
                  type="button"
                  onClick={handleAddTag}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors duration-200"
                >
                  Add
                </button>
              </div>
              {errors.tags && (
                <p className="mt-1 text-sm text-red-400">{errors.tags}</p>
              )}
              <div className="flex flex-wrap gap-2 mt-2">
                {formData.tags?.map((tag, index) => (
                  <span
                    key={index}
                    className="inline-flex items-center px-3 py-1 bg-blue-900/50 border border-blue-500/50 rounded-full text-blue-200 text-sm"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => handleRemoveTag(tag)}
                      className="ml-2 text-blue-400 hover:text-blue-200"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Deployment Notes */}
            <div>
              <label htmlFor="deployment_notes" className="block text-sm font-medium text-gray-300 mb-2">
                Deployment Notes (Markdown supported, max 50,000 chars)
              </label>
              <textarea
                id="deployment_notes"
                name="deployment_notes"
                value={formData.deployment_notes}
                onChange={handleInputChange}
                onBlur={handleBlur}
                rows={6}
                className={`w-full px-4 py-2 bg-gray-700 border ${
                  errors.deployment_notes && touched.deployment_notes ? 'border-red-500' : 'border-gray-600'
                } rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent`}
                placeholder="# Software Installed&#10;- Nginx 1.20&#10;- Node.js 18.x"
              />
              {errors.deployment_notes && touched.deployment_notes && (
                <p className="mt-1 text-sm text-red-400">{errors.deployment_notes}</p>
              )}
            </div>

            {/* Submit Error */}
            {errors.submit && (
              <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-4">
                <p className="text-red-200 text-sm">{errors.submit}</p>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-4 pt-4">
              <button
                type="submit"
                disabled={createVMMutation.isPending}
                className="flex-1 px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors duration-200 font-medium"
              >
                {createVMMutation.isPending ? 'Creating...' : 'Create VM'}
              </button>
              <button
                type="button"
                onClick={handleCancel}
                disabled={createVMMutation.isPending}
                className="flex-1 px-6 py-3 bg-gray-600 hover:bg-gray-700 disabled:bg-gray-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors duration-200 font-medium"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
