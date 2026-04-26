"""
Integration tests for Docker deployment configuration.

These tests verify that the Docker configuration is valid and services
can communicate properly.
"""

import pytest
import subprocess
import time
import requests
from typing import Dict, List


class TestDockerConfiguration:
    """Test Docker configuration files and deployment."""

    def test_dockerfile_exists(self):
        """Verify Dockerfile exists."""
        import os
        assert os.path.exists("Dockerfile"), "Dockerfile not found"

    def test_docker_compose_dev_exists(self):
        """Verify docker-compose.yml exists."""
        import os
        assert os.path.exists("docker-compose.yml"), "docker-compose.yml not found"

    def test_docker_compose_prod_exists(self):
        """Verify docker-compose.prod.yml exists."""
        import os
        assert os.path.exists("docker-compose.prod.yml"), "docker-compose.prod.yml not found"

    def test_dockerignore_exists(self):
        """Verify .dockerignore exists."""
        import os
        assert os.path.exists(".dockerignore"), ".dockerignore not found"

    def test_docker_compose_syntax_valid(self):
        """Verify docker-compose.yml has valid syntax."""
        result = subprocess.run(
            ["docker-compose", "config", "--quiet"],
            capture_output=True,
            text=True
        )
        # Exit code 0 means valid syntax
        assert result.returncode == 0, f"docker-compose.yml syntax error: {result.stderr}"

    def test_docker_compose_has_required_services(self):
        """Verify docker-compose.yml defines all required services."""
        result = subprocess.run(
            ["docker-compose", "config", "--services"],
            capture_output=True,
            text=True
        )
        
        services = result.stdout.strip().split("\n")
        required_services = ["postgres", "redis", "api", "celery-worker", "celery-beat"]
        
        for service in required_services:
            assert service in services, f"Required service '{service}' not found in docker-compose.yml"

    def test_dockerfile_has_required_instructions(self):
        """Verify Dockerfile contains required instructions."""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        required_instructions = [
            "FROM python:",
            "WORKDIR /app",
            "COPY requirements.txt",
            "RUN pip install",
            "EXPOSE 8000",
            "CMD"
        ]
        
        for instruction in required_instructions:
            assert instruction in content, f"Dockerfile missing required instruction: {instruction}"

    def test_dockerignore_excludes_sensitive_files(self):
        """Verify .dockerignore excludes sensitive files."""
        with open(".dockerignore", "r") as f:
            content = f.read()
        
        sensitive_patterns = [".env", ".git", "__pycache__", "*.pyc"]
        
        for pattern in sensitive_patterns:
            assert pattern in content, f".dockerignore should exclude: {pattern}"

    def test_production_env_example_exists(self):
        """Verify production environment example file exists."""
        import os
        assert os.path.exists(".env.production.example"), ".env.production.example not found"

    def test_production_env_has_required_variables(self):
        """Verify production environment example has all required variables."""
        with open(".env.production.example", "r") as f:
            content = f.read()
        
        required_vars = [
            "POSTGRES_PASSWORD",
            "REDIS_PASSWORD",
            "SECRET_KEY",
            "ENCRYPTION_MASTER_KEY",
            "DATABASE_URL",
            "REDIS_URL"
        ]
        
        for var in required_vars:
            assert var in content, f".env.production.example missing required variable: {var}"

    def test_docker_deployment_documentation_exists(self):
        """Verify Docker deployment documentation exists."""
        import os
        assert os.path.exists("DOCKER_DEPLOYMENT.md"), "DOCKER_DEPLOYMENT.md not found"

    def test_docker_quickstart_scripts_exist(self):
        """Verify Docker quickstart scripts exist."""
        import os
        assert os.path.exists("scripts/docker-quickstart.sh"), "docker-quickstart.sh not found"
        assert os.path.exists("scripts/docker-quickstart.ps1"), "docker-quickstart.ps1 not found"


@pytest.mark.skipif(
    subprocess.run(["docker", "info"], capture_output=True).returncode != 0,
    reason="Docker is not running"
)
class TestDockerServices:
    """Test Docker services when Docker is available."""

    @pytest.fixture(scope="class")
    def docker_services(self):
        """Start Docker services for testing."""
        # Check if services are already running
        result = subprocess.run(
            ["docker-compose", "ps", "-q"],
            capture_output=True,
            text=True
        )
        
        services_running = bool(result.stdout.strip())
        
        if not services_running:
            # Start services
            subprocess.run(["docker-compose", "up", "-d"], check=True)
            time.sleep(15)  # Wait for services to be healthy
        
        yield
        
        # Cleanup is optional - leave services running for development

    def test_postgres_service_healthy(self, docker_services):
        """Verify PostgreSQL service is healthy."""
        result = subprocess.run(
            ["docker-compose", "ps", "postgres"],
            capture_output=True,
            text=True
        )
        
        assert "Up" in result.stdout, "PostgreSQL service is not running"
        assert "healthy" in result.stdout or "Up" in result.stdout

    def test_redis_service_healthy(self, docker_services):
        """Verify Redis service is healthy."""
        result = subprocess.run(
            ["docker-compose", "ps", "redis"],
            capture_output=True,
            text=True
        )
        
        assert "Up" in result.stdout, "Redis service is not running"

    def test_api_service_healthy(self, docker_services):
        """Verify API service is healthy and responding."""
        max_retries = 5
        for i in range(max_retries):
            try:
                response = requests.get("http://localhost:8000/health", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    assert data["success"] is True
                    assert data["data"]["status"] == "healthy"
                    return
            except requests.exceptions.RequestException:
                if i < max_retries - 1:
                    time.sleep(3)
                    continue
                raise
        
        pytest.fail("API service did not become healthy")

    def test_celery_worker_running(self, docker_services):
        """Verify Celery worker is running."""
        result = subprocess.run(
            ["docker-compose", "ps", "celery-worker"],
            capture_output=True,
            text=True
        )
        
        assert "Up" in result.stdout, "Celery worker is not running"

    def test_celery_beat_running(self, docker_services):
        """Verify Celery beat scheduler is running."""
        result = subprocess.run(
            ["docker-compose", "ps", "celery-beat"],
            capture_output=True,
            text=True
        )
        
        assert "Up" in result.stdout, "Celery beat is not running"

    def test_services_can_communicate(self, docker_services):
        """Verify services can communicate with each other."""
        # Test API can reach database
        response = requests.get("http://localhost:8000/health/detailed", timeout=5)
        assert response.status_code == 200
        
        data = response.json()
        assert data["data"]["database"]["connected"] is True, "API cannot connect to database"
