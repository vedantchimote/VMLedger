/**
 * Validation utilities for form inputs
 * Based on VMLedger requirements
 */

/**
 * Validate IP address (IPv4 or IPv6)
 * Requirement 1.2: IP address must be valid IPv4 or IPv6 format
 */
export function isValidIPAddress(ip: string): boolean {
  // IPv4 regex
  const ipv4Regex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
  
  // IPv6 regex (simplified)
  const ipv6Regex = /^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}$|^[0-9a-fA-F]{1,4}::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}$/;
  
  return ipv4Regex.test(ip) || ipv6Regex.test(ip);
}

/**
 * Validate SSH port range
 * Requirement 1.3: SSH port must be between 1 and 65535
 */
export function isValidSSHPort(port: number): boolean {
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}

/**
 * Validate password complexity
 * Requirement 10.5: Minimum 12 characters, mixed case, numbers, special characters
 * Maximum 72 bytes (bcrypt limitation)
 */
export function isValidPassword(password: string): boolean {
  if (password.length < 12) return false;
  
  // Check bcrypt byte limit (72 bytes)
  const passwordBytes = new TextEncoder().encode(password).length;
  if (passwordBytes > 72) return false;
  
  const hasUpperCase = /[A-Z]/.test(password);
  const hasLowerCase = /[a-z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSpecialChar = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password);
  
  return hasUpperCase && hasLowerCase && hasNumber && hasSpecialChar;
}

/**
 * Get password strength feedback
 */
export function getPasswordStrength(password: string): {
  strength: 'weak' | 'medium' | 'strong';
  feedback: string[];
} {
  const feedback: string[] = [];
  
  if (password.length < 12) {
    feedback.push('Password must be at least 12 characters');
  }
  
  // Check bcrypt byte limit
  const passwordBytes = new TextEncoder().encode(password).length;
  if (passwordBytes > 72) {
    feedback.push(`Password is too long (${passwordBytes} bytes, max 72 bytes)`);
  }
  
  if (!/[A-Z]/.test(password)) {
    feedback.push('Add at least one uppercase letter');
  }
  
  if (!/[a-z]/.test(password)) {
    feedback.push('Add at least one lowercase letter');
  }
  
  if (!/[0-9]/.test(password)) {
    feedback.push('Add at least one number');
  }
  
  if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
    feedback.push('Add at least one special character');
  }
  
  const strength = feedback.length === 0 ? 'strong' : feedback.length <= 2 ? 'medium' : 'weak';
  
  return { strength, feedback };
}

/**
 * Validate email format
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validate hostname
 * Max 255 characters, alphanumeric + hyphens
 */
export function isValidHostname(hostname: string): boolean {
  if (hostname.length === 0 || hostname.length > 255) return false;
  
  const hostnameRegex = /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,253}[a-zA-Z0-9])?$/;
  return hostnameRegex.test(hostname);
}

/**
 * Validate deployment notes length
 * Requirement 6.4: Max 50,000 characters
 */
export function isValidDeploymentNotes(notes: string): boolean {
  return notes.length <= 50000;
}

/**
 * Validate webhook URL
 */
export function isValidWebhookURL(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

/**
 * Validate cooldown period (1-1440 minutes)
 */
export function isValidCooldownPeriod(minutes: number): boolean {
  return Number.isInteger(minutes) && minutes >= 1 && minutes <= 1440;
}

/**
 * Validate tags array
 * Max 20 tags per VM
 */
export function isValidTags(tags: string[]): boolean {
  return tags.length <= 20;
}

/**
 * Validate SSH private key format
 * Requirement 2.5: SSH key must be valid RSA, DSA, ECDSA, or Ed25519 format
 * Basic validation - checks for common SSH key headers
 */
export function isValidSSHKey(key: string): boolean {
  if (!key || key.trim().length === 0) return false;
  
  const trimmedKey = key.trim();
  
  // Check for common SSH private key headers
  const validHeaders = [
    '-----BEGIN RSA PRIVATE KEY-----',
    '-----BEGIN DSA PRIVATE KEY-----',
    '-----BEGIN EC PRIVATE KEY-----',
    '-----BEGIN OPENSSH PRIVATE KEY-----',
    '-----BEGIN PRIVATE KEY-----',
  ];
  
  const hasValidHeader = validHeaders.some(header => trimmedKey.startsWith(header));
  
  if (!hasValidHeader) return false;
  
  // Check for corresponding footer
  const validFooters = [
    '-----END RSA PRIVATE KEY-----',
    '-----END DSA PRIVATE KEY-----',
    '-----END EC PRIVATE KEY-----',
    '-----END OPENSSH PRIVATE KEY-----',
    '-----END PRIVATE KEY-----',
  ];
  
  const hasValidFooter = validFooters.some(footer => trimmedKey.endsWith(footer));
  
  return hasValidFooter;
}
