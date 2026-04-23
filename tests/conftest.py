"""
Pytest configuration and shared fixtures.
"""

import pytest
import secrets
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from vmledger.database import Base
from vmledger.main import app
from vmledger.models.user import User
from vmledger.models.vm import VM


@pytest.fixture(scope="session")
def test_engine():
    """Create in-memory SQLite engine for testing with PostgreSQL type emulation."""
    from sqlalchemy import event, TEXT
    import json
    
    # Create engine
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    
    # Enable foreign keys
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    # Temporarily replace ARRAY and TSVECTOR types for table creation
    from vmledger.models import vm as vm_module
    from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
    
    # Store original column definitions
    original_tags = vm_module.VM.tags
    original_search_vector = vm_module.VM.search_vector
    
    # Replace with TEXT for SQLite
    from sqlalchemy import Column
    vm_module.VM.__table__.c.tags.type = TEXT()
    vm_module.VM.__table__.c.search_vector.type = TEXT()
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Add event listeners to handle JSON serialization for tags
    @event.listens_for(vm_module.VM, 'before_insert', propagate=True)
    @event.listens_for(vm_module.VM, 'before_update', propagate=True)
    def serialize_tags(mapper, connection, target):
        if target.tags is not None and not isinstance(target.tags, str):
            target.tags = json.dumps(target.tags)
    
    @event.listens_for(vm_module.VM, 'load', propagate=True)
    def deserialize_tags(target, context):
        if target.tags is not None and isinstance(target.tags, str):
            try:
                target.tags = json.loads(target.tags)
            except (json.JSONDecodeError, TypeError):
                target.tags = []
    
    yield engine
    
    # Clean up
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create a new database session for each test."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        # Clean up all data after each test
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        db.close()


@pytest.fixture(scope="function")
def test_db(db_session):
    """Alias for db_session for backward compatibility."""
    return db_session


@pytest.fixture(scope="function")
def test_user(db_session):
    """Create a test user with encryption salt."""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="$2b$12$dummy_hash",  # Dummy bcrypt hash
        encryption_salt=secrets.token_hex(32),  # 64-character hex string
        is_active=True,
        failed_login_attempts=0
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_user2(db_session):
    """Create a second test user for isolation testing."""
    user = User(
        username="testuser2",
        email="test2@example.com",
        password_hash="$2b$12$dummy_hash2",
        encryption_salt=secrets.token_hex(32),
        is_active=True,
        failed_login_attempts=0
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_vm(db_session, test_user):
    """Create a test VM for credential tests."""
    from vmledger.models.vm import VM
    
    # Create a real VM in the database
    vm = VM(
        user_id=test_user.id,
        ip_address="192.168.1.100",
        hostname="test-server",
        ssh_port=22,
        tags=[],
        deployment_notes="",
        is_reachable=True
    )
    db_session.add(vm)
    db_session.commit()
    db_session.refresh(vm)
    
    yield vm
    
    # Cleanup
    db_session.delete(vm)
    db_session.commit()


@pytest.fixture(scope="function")
def client():
    """Create FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


# TODO: Add more fixtures as needed
# - test_credentials: Create test credentials
# - mock_ssh_server: Mock SSH server for testing
# - mock_redis: Mock Redis for testing
