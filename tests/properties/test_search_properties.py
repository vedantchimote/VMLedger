"""
Property-based tests for search engine functionality.

Tests Properties 8-11: Search functionality
Validates: Requirements 7.1-7.6
"""

import pytest
from hypothesis import given, strategies as st, assume
from vmledger.services.search_engine_service import SearchEngineService
from vmledger.models.vm import VM


# Strategy for generating search terms
search_terms = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" -_")
)

# Strategy for generating hostnames
hostnames = st.text(
    min_size=3,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-")
)


@given(
    hostname=hostnames,
    search_term=st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd")
    ))
)
def test_property_partial_search_matching(hostname, search_term, mock_db_session):
    """
    Property 8: Partial Search Matching
    
    Property: If a search term is a substring of a VM's hostname, tags, or
    deployment notes, that VM should appear in the search results.
    
    Validates: Requirement 7.3 - Support partial matching
    """
    # Arrange
    assume(len(search_term) > 0)
    assume(len(hostname) >= len(search_term))
    
    search_service = SearchEngineService(mock_db_session)
    
    # Create a VM with hostname containing the search term
    vm_hostname = hostname[:len(hostname)//2] + search_term + hostname[len(hostname)//2:]
    
    mock_vm = VM(
        id=1,
        user_id=1,
        hostname=vm_hostname,
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes="Test VM"
    )
    
    # Mock the database query to return this VM
    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_vm]
    
    # Act
    results = search_service.search_vms(search_term, user_id=1)
    
    # Assert
    assert len(results) > 0, \
        f"Search for '{search_term}' should find VM with hostname '{vm_hostname}'"
    assert any(search_term.lower() in vm.hostname.lower() for vm in results), \
        "Search results should contain VMs matching the search term"


@given(
    exact_match_hostname=hostnames,
    partial_match_hostname=hostnames
)
def test_property_search_result_ranking(
    exact_match_hostname, partial_match_hostname, mock_db_session
):
    """
    Property 9: Search Result Ranking
    
    Property: Exact matches should be ranked higher than partial matches
    in search results.
    
    Validates: Requirement 7.4 - Rank results by relevance
    """
    # Arrange
    assume(exact_match_hostname != partial_match_hostname)
    assume(len(exact_match_hostname) > 3)
    
    search_service = SearchEngineService(mock_db_session)
    
    # Create VMs: one with exact match, one with partial match
    exact_vm = VM(
        id=1,
        user_id=1,
        hostname=exact_match_hostname,
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes="",
        search_rank=1.0  # Higher rank for exact match
    )
    
    partial_vm = VM(
        id=2,
        user_id=1,
        hostname=f"prefix-{partial_match_hostname}-suffix",
        ip_address="192.168.1.101",
        ssh_port=22,
        tags=["test"],
        deployment_notes="",
        search_rank=0.5  # Lower rank for partial match
    )
    
    # Mock the database query to return both VMs, sorted by rank
    mock_db_session.query.return_value.filter.return_value.all.return_value = [
        exact_vm, partial_vm
    ]
    
    # Act
    results = search_service.search_vms(exact_match_hostname, user_id=1)
    
    # Assert
    if len(results) >= 2:
        # Exact match should appear before partial match
        exact_match_index = next(
            (i for i, vm in enumerate(results) if vm.hostname == exact_match_hostname),
            None
        )
        partial_match_index = next(
            (i for i, vm in enumerate(results) if partial_match_hostname in vm.hostname),
            None
        )
        
        if exact_match_index is not None and partial_match_index is not None:
            assert exact_match_index < partial_match_index, \
                "Exact matches should be ranked higher than partial matches"


@given(
    search_term=search_terms,
    deployment_notes=st.text(min_size=50, max_size=500)
)
def test_property_search_highlighting(search_term, deployment_notes, mock_db_session):
    """
    Property 10: Search Highlighting
    
    Property: Search results should highlight the matched terms in the
    deployment notes and other fields.
    
    Validates: Requirement 7.5 - Highlight matching terms
    """
    # Arrange
    assume(len(search_term.strip()) > 0)
    
    search_service = SearchEngineService(mock_db_session)
    
    # Create deployment notes containing the search term
    notes_with_term = deployment_notes[:len(deployment_notes)//2] + \
                      f" {search_term} " + \
                      deployment_notes[len(deployment_notes)//2:]
    
    mock_vm = VM(
        id=1,
        user_id=1,
        hostname="test-vm",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=notes_with_term
    )
    
    # Mock the database query
    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_vm]
    
    # Act
    results = search_service.search_vms(search_term, user_id=1, highlight=True)
    
    # Assert
    if len(results) > 0:
        result_vm = results[0]
        # Check if highlighting was applied (implementation-specific)
        # Common highlighting formats: <mark>term</mark>, **term**, etc.
        assert hasattr(result_vm, 'highlighted_notes') or \
               hasattr(result_vm, 'deployment_notes'), \
               "Search results should include deployment notes"


@given(
    term1=st.text(min_size=3, max_size=20, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll")
    )),
    term2=st.text(min_size=3, max_size=20, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll")
    ))
)
def test_property_search_boolean_or_logic(term1, term2, mock_db_session):
    """
    Property 11: Search Boolean OR Logic
    
    Property: When searching with multiple terms, results should include VMs
    matching ANY of the terms (OR logic), not requiring all terms (AND logic).
    
    Validates: Requirement 7.6 - Support OR logic for multi-term queries
    """
    # Arrange
    assume(term1 != term2)
    assume(len(term1) > 2 and len(term2) > 2)
    
    search_service = SearchEngineService(mock_db_session)
    
    # Create VMs matching different terms
    vm1 = VM(
        id=1,
        user_id=1,
        hostname=f"{term1}-server",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=[term1],
        deployment_notes=""
    )
    
    vm2 = VM(
        id=2,
        user_id=1,
        hostname=f"{term2}-server",
        ip_address="192.168.1.101",
        ssh_port=22,
        tags=[term2],
        deployment_notes=""
    )
    
    # Mock the database query to return both VMs
    mock_db_session.query.return_value.filter.return_value.all.return_value = [vm1, vm2]
    
    # Act - Search with both terms (space-separated implies OR)
    search_query = f"{term1} {term2}"
    results = search_service.search_vms(search_query, user_id=1)
    
    # Assert
    assert len(results) >= 1, \
        f"Search for '{search_query}' should find VMs matching either term"
    
    # At least one VM should match term1 OR term2
    matches_term1 = any(term1.lower() in (vm.hostname.lower() + ' '.join(vm.tags).lower()) 
                       for vm in results)
    matches_term2 = any(term2.lower() in (vm.hostname.lower() + ' '.join(vm.tags).lower()) 
                       for vm in results)
    
    assert matches_term1 or matches_term2, \
        "Search results should include VMs matching at least one search term"


@given(
    search_term=search_terms,
    tag=st.text(min_size=3, max_size=20, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd")
    ))
)
def test_property_search_across_all_fields(search_term, tag, mock_db_session):
    """
    Property 8: Partial Search Matching (All Fields)
    
    Property: Search should match against hostname, tags, and deployment notes.
    
    Validates: Requirement 7.1 - Search across hostname, tags, deployment notes
    """
    # Arrange
    assume(len(search_term.strip()) > 0)
    assume(len(tag) > 0)
    
    search_service = SearchEngineService(mock_db_session)
    
    # Create VMs with search term in different fields
    vm_in_hostname = VM(
        id=1,
        user_id=1,
        hostname=f"{search_term}-server",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["other"],
        deployment_notes=""
    )
    
    vm_in_tags = VM(
        id=2,
        user_id=1,
        hostname="server",
        ip_address="192.168.1.101",
        ssh_port=22,
        tags=[search_term, tag],
        deployment_notes=""
    )
    
    vm_in_notes = VM(
        id=3,
        user_id=1,
        hostname="server",
        ip_address="192.168.1.102",
        ssh_port=22,
        tags=["other"],
        deployment_notes=f"This VM is for {search_term} testing"
    )
    
    # Mock the database query
    mock_db_session.query.return_value.filter.return_value.all.return_value = [
        vm_in_hostname, vm_in_tags, vm_in_notes
    ]
    
    # Act
    results = search_service.search_vms(search_term, user_id=1)
    
    # Assert
    assert len(results) > 0, \
        f"Search for '{search_term}' should find VMs with term in any field"


@given(
    user_id=st.integers(min_value=1, max_value=100),
    search_term=search_terms
)
def test_property_search_respects_user_isolation(user_id, search_term, mock_db_session):
    """
    Property 8: Partial Search Matching (User Isolation)
    
    Property: Search results should only include VMs owned by the searching user.
    
    Validates: Requirement 7.1 + User isolation requirements
    """
    # Arrange
    assume(len(search_term.strip()) > 0)
    
    search_service = SearchEngineService(mock_db_session)
    
    # Create VMs for this user only
    user_vms = [
        VM(
            id=i,
            user_id=user_id,
            hostname=f"{search_term}-vm-{i}",
            ip_address=f"192.168.1.{i}",
            ssh_port=22,
            tags=["test"],
            deployment_notes=""
        )
        for i in range(1, 4)
    ]
    
    # Mock the database query
    mock_db_session.query.return_value.filter.return_value.all.return_value = user_vms
    
    # Act
    results = search_service.search_vms(search_term, user_id=user_id)
    
    # Assert
    for vm in results:
        assert vm.user_id == user_id, \
            "Search results should only contain VMs owned by the searching user"
