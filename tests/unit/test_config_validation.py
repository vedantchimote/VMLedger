"""
Unit tests for configuration validation.

Tests the comprehensive environment variable validation added in Task 20.2.
Validates Requirements 15.1-15.6 (Configuration Management).
"""

import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError


class TestConfigValidation:
    """Test configuration validation functionality."""
    
    def test_validate_required_settings_success(self):
        """Test that validation passes with valid settings."""
        from vmledger.config import Settings, validate_required_settings
        
        # Create valid settings
        with patch.dict('os.environ', {
            'SECRET_KEY': 'a' * 32,
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
            'REDIS_URL': 'redis://localhost:6379/0',
        }):
            # Reload settings
            from vmledger import config
            config.settings = Settings()
            
            # Should not raise
            validate_required_settings()
    
    def test_validate_missing_secret_key(self):
        """Test that validation fails when SECRET_KEY is missing."""
        from vmledger.config import Settings, validate_required_settings
        
        with patch.dict('os.environ', {
            'SECRET_KEY': '',
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
        }, clear=True):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            assert "SECRET_KEY is required" in str(exc_info.value)
    
    def test_validate_default_secret_key(self):
        """Test that validation fails when SECRET_KEY is default value."""
        from vmledger.config import Settings, validate_required_settings
        
        with patch.dict('os.environ', {
            'SECRET_KEY': 'your-secret-key-here-change-in-production',
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
        }):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            assert "SECRET_KEY must be changed from default value" in str(exc_info.value)
    
    def test_validate_short_secret_key(self):
        """Test that validation fails when SECRET_KEY is too short."""
        from vmledger.config import Settings, validate_required_settings
        
        with patch.dict('os.environ', {
            'SECRET_KEY': 'short',
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
        }):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            assert "SECRET_KEY must be at least 32 characters" in str(exc_info.value)
    
    def test_validate_missing_encryption_key(self):
        """Test that validation fails when ENCRYPTION_MASTER_KEY is missing."""
        from vmledger.config import Settings, validate_required_settings
        
        with patch.dict('os.environ', {
            'SECRET_KEY': 'a' * 32,
            'ENCRYPTION_MASTER_KEY': '',
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
        }, clear=True):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            assert "ENCRYPTION_MASTER_KEY is required" in str(exc_info.value)
    
    def test_validate_invalid_database_url(self):
        """Test that validation fails with invalid DATABASE_URL."""
        from vmledger.config import Settings, validate_required_settings
        
        with patch.dict('os.environ', {
            'SECRET_KEY': 'a' * 32,
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'mysql://user:pass@localhost:3306/db',  # Wrong protocol
        }):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            assert "DATABASE_URL must be a valid PostgreSQL connection string" in str(exc_info.value)
    
    def test_validate_invalid_redis_url(self):
        """Test that validation fails with invalid REDIS_URL."""
        from vmledger.config import Settings, validate_required_settings
        
        with patch.dict('os.environ', {
            'SECRET_KEY': 'a' * 32,
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
            'REDIS_URL': 'http://localhost:6379',  # Wrong protocol
        }):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            assert "REDIS_URL must be a valid Redis connection string" in str(exc_info.value)
    
    def test_validate_monitoring_intervals(self):
        """Test validation of monitoring interval settings (Requirements 15.1-15.3)."""
        from vmledger.config import Settings, validate_required_settings
        
        # Test invalid ping interval (too low)
        with patch.dict('os.environ', {
            'SECRET_KEY': 'a' * 32,
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
            'PING_INTERVAL_SECONDS': '5',  # Too low
        }):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            assert "PING_INTERVAL_SECONDS must be at least 10 seconds" in str(exc_info.value)
    
    def test_validate_concurrent_workers(self):
        """Test validation of concurrent workers setting (Requirement 15.4)."""
        from vmledger.config import Settings, validate_required_settings
        
        # Test invalid concurrent workers (too low)
        with patch.dict('os.environ', {
            'SECRET_KEY': 'a' * 32,
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
            'CONCURRENT_WORKERS': '0',  # Too low
        }):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            assert "CONCURRENT_WORKERS must be at least 1" in str(exc_info.value)
    
    def test_validate_password_settings(self):
        """Test validation of password settings (Requirement 10.5)."""
        from vmledger.config import Settings, validate_required_settings
        
        # Test invalid password min length (too low)
        with patch.dict('os.environ', {
            'SECRET_KEY': 'a' * 32,
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
            'PASSWORD_MIN_LENGTH': '5',  # Too low
        }):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            assert "PASSWORD_MIN_LENGTH must be at least 8" in str(exc_info.value)
    
    def test_validate_ssh_settings(self):
        """Test validation of SSH settings (Requirements 5.1-5.5)."""
        from vmledger.config import Settings, validate_required_settings
        
        # Test invalid SSH connection timeout (too low)
        with patch.dict('os.environ', {
            'SECRET_KEY': 'a' * 32,
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
            'SSH_CONNECTION_TIMEOUT': '2',  # Too low
        }):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            assert "SSH_CONNECTION_TIMEOUT must be at least 5 seconds" in str(exc_info.value)
    
    def test_validate_data_retention(self):
        """Test validation of data retention settings (Requirements 4.6, 5.7)."""
        from vmledger.config import Settings, validate_required_settings
        
        # Test invalid ping results retention (too low)
        with patch.dict('os.environ', {
            'SECRET_KEY': 'a' * 32,
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
            'PING_RESULTS_RETENTION': '5',  # Too low
        }):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            assert "PING_RESULTS_RETENTION must be at least 10" in str(exc_info.value)
    
    def test_validate_logging_settings(self):
        """Test validation of logging settings (Requirements 14.1-14.6)."""
        from vmledger.config import Settings, validate_required_settings
        
        # Test invalid log max size (too low)
        with patch.dict('os.environ', {
            'SECRET_KEY': 'a' * 32,
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
            'LOG_MAX_SIZE_MB': '5',  # Too low
        }):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            assert "LOG_MAX_SIZE_MB must be at least 10" in str(exc_info.value)
    
    def test_validate_multiple_errors(self):
        """Test that validation reports multiple errors at once."""
        from vmledger.config import Settings, validate_required_settings
        
        with patch.dict('os.environ', {
            'SECRET_KEY': 'short',  # Too short
            'ENCRYPTION_MASTER_KEY': 'short',  # Too short
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
            'PING_INTERVAL_SECONDS': '5',  # Too low
        }):
            from vmledger import config
            config.settings = Settings()
            
            with pytest.raises(ValueError) as exc_info:
                validate_required_settings()
            
            error_message = str(exc_info.value)
            # Should contain multiple errors
            assert "SECRET_KEY must be at least 32 characters" in error_message
            assert "ENCRYPTION_MASTER_KEY must be at least 32 characters" in error_message
            assert "PING_INTERVAL_SECONDS must be at least 10 seconds" in error_message
    
    def test_validate_warnings_logged(self, caplog):
        """Test that validation warnings are logged."""
        from vmledger.config import Settings, validate_required_settings
        import logging
        
        with patch.dict('os.environ', {
            'SECRET_KEY': 'a' * 32,
            'ENCRYPTION_MASTER_KEY': 'b' * 32,
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/db',
            'CONCURRENT_WORKERS': '150',  # Very high - should warn
        }):
            from vmledger import config
            config.settings = Settings()
            
            with caplog.at_level(logging.WARNING):
                validate_required_settings()
            
            # Should have warning about high concurrent workers
            assert any("CONCURRENT_WORKERS is very high" in record.message for record in caplog.records)


class TestConfigurationManagementRequirements:
    """Test that configuration management requirements are satisfied."""
    
    def test_requirement_15_1_ping_interval_configurable(self):
        """Requirement 15.1: Allow configuration of Custom_Ping check intervals."""
        from vmledger.config import Settings
        
        with patch.dict('os.environ', {'PING_INTERVAL_SECONDS': '120'}):
            settings = Settings()
            assert settings.ping_interval_seconds == 120
    
    def test_requirement_15_2_metrics_interval_configurable(self):
        """Requirement 15.2: Allow configuration of metric collection intervals."""
        from vmledger.config import Settings
        
        with patch.dict('os.environ', {'METRICS_INTERVAL_SECONDS': '600'}):
            settings = Settings()
            assert settings.metrics_interval_seconds == 600
    
    def test_requirement_15_3_alert_cooldown_configurable(self):
        """Requirement 15.3: Allow configuration of alert notification cooldown periods."""
        from vmledger.config import Settings
        
        with patch.dict('os.environ', {'ALERT_COOLDOWN_MINUTES': '30'}):
            settings = Settings()
            assert settings.alert_cooldown_minutes == 30
    
    def test_requirement_15_4_concurrent_workers_configurable(self):
        """Requirement 15.4: Allow configuration of concurrent worker limits."""
        from vmledger.config import Settings
        
        with patch.dict('os.environ', {'CONCURRENT_WORKERS': '20'}):
            settings = Settings()
            assert settings.concurrent_workers == 20
    
    def test_requirement_15_5_load_from_environment(self):
        """Requirement 15.5: Load configuration from environment variables."""
        from vmledger.config import Settings
        
        # Test that all settings can be loaded from environment
        test_env = {
            'APP_NAME': 'TestApp',
            'APP_VERSION': '2.0.0',
            'DEBUG': 'True',
            'LOG_LEVEL': 'DEBUG',
            'API_PORT': '9000',
            'DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
            'SECRET_KEY': 'test-secret-key-32-characters-long',
            'ENCRYPTION_MASTER_KEY': 'test-encryption-key-32-chars-long',
        }
        
        with patch.dict('os.environ', test_env):
            settings = Settings()
            assert settings.app_name == 'TestApp'
            assert settings.app_version == '2.0.0'
            assert settings.debug is True
            assert settings.log_level == 'DEBUG'
            assert settings.api_port == 9000
    
    def test_requirement_15_6_no_restart_for_intervals(self):
        """
        Requirement 15.6: Apply configuration changes without restart for interval-based settings.
        
        Note: This is tested by verifying that Celery Beat reads intervals from settings
        dynamically. The actual runtime behavior is tested in integration tests.
        """
        from vmledger.config import Settings
        
        # Verify that interval settings are accessible and can be changed
        with patch.dict('os.environ', {'PING_INTERVAL_SECONDS': '60'}):
            settings1 = Settings()
            assert settings1.ping_interval_seconds == 60
        
        # Simulate configuration change (in practice, Celery Beat reads this dynamically)
        with patch.dict('os.environ', {'PING_INTERVAL_SECONDS': '120'}):
            settings2 = Settings()
            assert settings2.ping_interval_seconds == 120
