'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAuth } from '@/lib/hooks/use-auth';
import { useVM, useUpdateVM, useDeleteVM } from '@/lib/hooks/use-vms';
import {
  isValidIPAddress,
  isValidSSHPort,
  isValidHostname,
  isValidTags,
  isValidSSHKey,
} from '@/lib/validation';
import type { VMUpdateRequest } from '@/types/api';

export default function EditVMPage() {
  const router = useRouter();
  const params = useParams();
  const vmId = Number(params.id);
  
  const { isAuthenticated } = useAuth();
  const { data: vm, isLoading: isLoadingVM } = useVM(vmId);
  const updateVMMutation = useUpdateVM();
  const deleteVMMutation = useDeleteVM();

  // Form state
  const [formData, setFormData] = useState<VMUpdateRequest>({
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

  const [authMethod, setAuthMethod] = useState<'ssh_key' | 'password' | 'none'>('none');
  const [tagInput, setTagInput] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  
  // Deployment notes editor state
  const [notesTab, setNotesTab] = useState<'edit' | 'preview'>('edit');
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const autoSaveTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastSavedNotesRef = useRef<string>('');

  // Populate form with existing VM data
  useEffect(() => {
    if (vm) {
      setFormData({
        ip_address: vm.ip_address,
        hostname: vm.hostname,
        domain: vm.domain || '',
        ssh_port: vm.ssh_port,
        tags: vm.tags || [],
        deployment_notes: vm.deployment_notes || '',
        ssh_username: 'root', // Default, will be updated if needed
      });
      // Initialize last saved notes
      lastSavedNotesRef.current = vm.deployment_notes || '';
    }
  }, [vm]);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  // Auto-save deployment notes
  const autoSaveNotes = useCallback(async (notes: string) => {
    if (notes === lastSavedNotesRef.current) {
      return; // No changes, skip save
    }

    setAutoSaveStatus('saving');
    
    try {
      await updateVMMutation.mutateAsync({
        vmId,
        vmData: { deployment_notes: notes },
      });
      lastSavedNotesRef.current = notes;
      setAutoSaveStatus('saved');
      
      // Reset to idle after 2 seconds
      setTimeout(() => {
        setAutoSaveStatus('idle');
      }, 2000);
    } catch (error) {
      console.error('Auto-save failed:', error);
      setAutoSaveStatus('error');
      
      // Reset to idle after 3 seconds
      setTimeout(() => {
        setAutoSaveStatus('idle');
      }, 3000);
    }
  }, [vmId, updateVMMutation]);

  // Debounced auto-save effect
  useEffect(() => {
    const notes = formData.deployment_notes || '';
    
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

  if (!isAuthenticated) {
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
        if (authMethod !== 'none' && !stringValue) return 'SSH username is required';
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
      'deployment_notes',
    ];

    if (authMethod !== 'none') {
      fieldsToValidate.push('ssh_username');
      if (authMethod === 'ssh_key') {
        fieldsToValidate.push('ssh_private_key');
      } else if (authMethod === 'password') {
        fieldsToValidate.push('ssh_password');
      }
    }

    fieldsToValidate.forEach(field => {
      const error = validateField(field, formData[field as keyof VMUpdateRequest]);
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
    const submitData: VMUpdateRequest = {
      ip_address: formData.ip_address,
      hostname: formData.hostname,
      domain: formData.domain || undefined,
      ssh_port: Number(formData.ssh_port),
      tags: formData.tags || [],
      deployment_notes: formData.deployment_notes || undefined,
    };

    // Only include credentials if updating them
    if (authMethod === 'ssh_key') {
      submitData.ssh_username = formData.ssh_username;
      submitData.ssh_private_key = formData.ssh_private_key;
    } else if (authMethod === 'password') {
      submitData.ssh_username = formData.ssh_username;
      submitData.ssh_password = formData.ssh_password;
    }

    try {
      await updateVMMutation.mutateAsync({ vmId, vmData: submitData });
      router.push('/dashboard');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to update VM';
      setErrors(prev => ({
        ...prev,
        submit: errorMessage,
      }));
    }
  };

  const handleDelete = async () => {
    try {
      await deleteVMMutation.mutateAsync(vmId);
      router.push('/dashboard');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete VM';
      setErrors(prev => ({
        ...prev,
        submit: errorMessage,
      }));
      setShowDeleteConfirm(false);
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
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-3xl font-bold text-white">Edit VM</h2>
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors duration-200 text-sm font-medium"
            >
              Delete VM
            </button>
          </div>

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

            {/* Update Credentials Section */}
            <div className="border-t border-gray-700 pt-6">
              <h3 className="text-xl font-semibold text-white mb-4">Update Credentials (Optional)</h3>
              
              {/* Authentication Method */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Update Authentication
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center">
                    <input
                      type="radio"
                      name="auth_method"
                      value="none"
                      checked={authMethod === 'none'}
                      onChange={() => setAuthMethod('none')}
                      className="mr-2"
                    />
                    <span className="text-gray-300">Keep Existing</span>
                  </label>
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

              {/* SSH Username (conditional) */}
              {authMethod !== 'none' && (
                <div className="mb-4">
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
              )}

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
            </div>

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
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-300">
                  Deployment Notes (Markdown supported, max 50,000 chars)
                </label>
                <div className="flex items-center gap-4">
                  {/* Auto-save status indicator */}
                  <div className="text-xs">
                    {autoSaveStatus === 'saving' && (
                      <span className="text-blue-400 flex items-center gap-1">
                        <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Saving...
                      </span>
                    )}
                    {autoSaveStatus === 'saved' && (
                      <span className="text-green-400 flex items-center gap-1">
                        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        Saved
                      </span>
                    )}
                    {autoSaveStatus === 'error' && (
                      <span className="text-red-400 flex items-center gap-1">
                        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                        Failed to save
                      </span>
                    )}
                  </div>
                  {/* Character counter */}
                  <div className={`text-xs font-medium ${
                    (formData.deployment_notes?.length || 0) >= 49000
                      ? 'text-red-400'
                      : (formData.deployment_notes?.length || 0) >= 45000
                      ? 'text-yellow-400'
                      : 'text-gray-400'
                  }`}>
                    {formData.deployment_notes?.length || 0} / 50,000 characters
                  </div>
                </div>
              </div>
              
              {/* Tab buttons */}
              <div className="flex border-b border-gray-600 mb-2">
                <button
                  type="button"
                  onClick={() => setNotesTab('edit')}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    notesTab === 'edit'
                      ? 'border-blue-500 text-blue-400'
                      : 'border-transparent text-gray-400 hover:text-gray-300'
                  }`}
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => setNotesTab('preview')}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    notesTab === 'preview'
                      ? 'border-blue-500 text-blue-400'
                      : 'border-transparent text-gray-400 hover:text-gray-300'
                  }`}
                >
                  Preview
                </button>
              </div>

              {/* Tab content */}
              {notesTab === 'edit' ? (
                <textarea
                  id="deployment_notes"
                  name="deployment_notes"
                  value={formData.deployment_notes}
                  onChange={handleInputChange}
                  onBlur={handleBlur}
                  rows={12}
                  className={`w-full px-4 py-2 bg-gray-700 border ${
                    errors.deployment_notes && touched.deployment_notes ? 'border-red-500' : 'border-gray-600'
                  } rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm`}
                  placeholder="# Software Installed&#10;- Nginx 1.20&#10;- Node.js 18.x&#10;&#10;## Configuration&#10;- SSL enabled&#10;- Port 443"
                />
              ) : (
                <div className="min-h-[300px] px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg overflow-auto">
                  {formData.deployment_notes && formData.deployment_notes.trim() !== '' ? (
                    <div className="prose prose-invert prose-sm max-w-none">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          h1: ({ ...props }) => (
                            <h1 className="text-2xl font-bold text-white mb-4" {...props} />
                          ),
                          h2: ({ ...props }) => (
                            <h2 className="text-xl font-bold text-white mb-3 mt-6" {...props} />
                          ),
                          h3: ({ ...props }) => (
                            <h3 className="text-lg font-bold text-white mb-2 mt-4" {...props} />
                          ),
                          p: ({ ...props }) => <p className="text-gray-300 mb-4" {...props} />,
                          ul: ({ ...props }) => (
                            <ul className="list-disc list-inside text-gray-300 mb-4 space-y-1" {...props} />
                          ),
                          ol: ({ ...props }) => (
                            <ol className="list-decimal list-inside text-gray-300 mb-4 space-y-1" {...props} />
                          ),
                          li: ({ ...props }) => <li className="text-gray-300" {...props} />,
                          code: (props) => {
                            // eslint-disable-next-line @typescript-eslint/no-explicit-any
                            const { inline, ...rest } = props as { inline?: boolean; [key: string]: any };
                            return inline ? (
                              <code
                                className="bg-gray-600 text-blue-300 px-1.5 py-0.5 rounded text-sm"
                                {...rest}
                              />
                            ) : (
                              <code
                                className="block bg-gray-600 text-gray-200 p-4 rounded-lg overflow-x-auto text-sm"
                                {...rest}
                              />
                            );
                          },
                          pre: ({ ...props }) => (
                            <pre className="bg-gray-600 rounded-lg overflow-x-auto mb-4" {...props} />
                          ),
                          a: ({ ...props }) => (
                            <a className="text-blue-400 hover:text-blue-300 underline" {...props} />
                          ),
                          blockquote: ({ ...props }) => (
                            <blockquote
                              className="border-l-4 border-gray-500 pl-4 italic text-gray-400 mb-4"
                              {...props}
                            />
                          ),
                          strong: ({ ...props }) => (
                            <strong className="font-bold text-white" {...props} />
                          ),
                          em: ({ ...props }) => <em className="italic text-gray-300" {...props} />,
                        }}
                      >
                        {formData.deployment_notes}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-gray-400 text-sm italic">No content to preview</p>
                  )}
                </div>
              )}
              
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
                disabled={updateVMMutation.isPending}
                className="flex-1 px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors duration-200 font-medium"
              >
                {updateVMMutation.isPending ? 'Updating...' : 'Update VM'}
              </button>
              <button
                type="button"
                onClick={handleCancel}
                disabled={updateVMMutation.isPending}
                className="flex-1 px-6 py-3 bg-gray-600 hover:bg-gray-700 disabled:bg-gray-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors duration-200 font-medium"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </main>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg shadow-xl p-6 max-w-md w-full mx-4 border border-gray-700">
            <h3 className="text-xl font-bold text-white mb-4">Confirm Deletion</h3>
            <p className="text-gray-300 mb-2">
              Are you sure you want to delete <strong className="text-white">{vm.hostname}</strong>?
            </p>
            <p className="text-yellow-400 text-sm mb-6">
              Warning: This will permanently delete the VM, all associated credentials, monitoring data, and deployment notes. This action cannot be undone.
            </p>
            <div className="flex gap-4">
              <button
                onClick={handleDelete}
                disabled={deleteVMMutation.isPending}
                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors duration-200 font-medium"
              >
                {deleteVMMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleteVMMutation.isPending}
                className="flex-1 px-4 py-2 bg-gray-600 hover:bg-gray-700 disabled:bg-gray-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors duration-200 font-medium"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
