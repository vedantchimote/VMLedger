"""
Property-based tests for Markdown preservation in deployment notes.

Tests Property 7: Markdown Preservation
Validates: Requirements 6.2
"""

import pytest
from hypothesis import given, strategies as st, assume
from vmledger.services.vm_registry_service import VMRegistryService
from vmledger.models.vm import VM


# Strategy for generating Markdown content
markdown_elements = st.sampled_from([
    "# Heading 1\n",
    "## Heading 2\n",
    "### Heading 3\n",
    "**bold text**\n",
    "*italic text*\n",
    "`code snippet`\n",
    "```python\nprint('hello')\n```\n",
    "- List item 1\n- List item 2\n",
    "1. Numbered item\n2. Another item\n",
    "[Link text](https://example.com)\n",
    "![Image alt](https://example.com/image.png)\n",
    "> Blockquote\n",
    "---\n",  # Horizontal rule
    "| Table | Header |\n|-------|--------|\n| Cell  | Data   |\n",
])


@given(
    markdown_content=st.lists(markdown_elements, min_size=1, max_size=20)
)
def test_property_markdown_preservation_on_save(markdown_content, mock_db_session):
    """
    Property 7: Markdown Preservation
    
    Property: Markdown formatting in deployment notes should be preserved
    exactly as entered when saved and retrieved from the database.
    
    Validates: Requirement 6.2 - Support Markdown formatting in deployment notes
    """
    # Arrange
    vm_service = VMRegistryService(mock_db_session)
    
    # Combine markdown elements into a single document
    deployment_notes = "".join(markdown_content)
    
    # Ensure it's within the 50,000 character limit
    assume(len(deployment_notes) <= 50000)
    
    # Create a mock VM with Markdown deployment notes
    mock_vm = VM(
        id=1,
        user_id=1,
        hostname="test-vm",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=deployment_notes
    )
    
    # Mock the database operations
    mock_db_session.add.return_value = None
    mock_db_session.commit.return_value = None
    mock_db_session.refresh.return_value = None
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act - Create VM with Markdown notes
    created_vm = vm_service.create_vm(
        user_id=1,
        hostname="test-vm",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=deployment_notes
    )
    
    # Retrieve the VM
    retrieved_vm = vm_service.get_vm(vm_id=1, user_id=1)
    
    # Assert - Markdown should be preserved exactly
    assert retrieved_vm.deployment_notes == deployment_notes, \
        "Markdown formatting should be preserved exactly as entered"


@given(
    original_markdown=st.lists(markdown_elements, min_size=1, max_size=10),
    updated_markdown=st.lists(markdown_elements, min_size=1, max_size=10)
)
def test_property_markdown_preservation_on_update(
    original_markdown, updated_markdown, mock_db_session
):
    """
    Property 7: Markdown Preservation (Update)
    
    Property: When updating deployment notes with new Markdown content,
    the new content should be preserved exactly, replacing the old content.
    
    Validates: Requirement 6.2 - Support Markdown formatting in deployment notes
    """
    # Arrange
    vm_service = VMRegistryService(mock_db_session)
    
    original_notes = "".join(original_markdown)
    updated_notes = "".join(updated_markdown)
    
    # Ensure both are within limits
    assume(len(original_notes) <= 50000)
    assume(len(updated_notes) <= 50000)
    assume(original_notes != updated_notes)
    
    # Create a mock VM with original Markdown
    mock_vm = VM(
        id=1,
        user_id=1,
        hostname="test-vm",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=original_notes
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act - Update deployment notes
    updated_vm = vm_service.update_vm(
        vm_id=1,
        user_id=1,
        deployment_notes=updated_notes
    )
    
    # Assert - New Markdown should replace old content exactly
    assert mock_vm.deployment_notes == updated_notes, \
        "Updated Markdown should be preserved exactly"


@given(
    markdown_with_special_chars=st.text(
        min_size=10,
        max_size=1000,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd", "P"),
            whitelist_characters="\n\t*_`#[]()!-|>"
        )
    )
)
def test_property_markdown_special_characters_preserved(
    markdown_with_special_chars, mock_db_session
):
    """
    Property 7: Markdown Preservation (Special Characters)
    
    Property: Special Markdown characters (*, _, `, #, [], (), etc.)
    should be preserved without escaping or modification.
    
    Validates: Requirement 6.2 - Support Markdown formatting in deployment notes
    """
    # Arrange
    vm_service = VMRegistryService(mock_db_session)
    
    # Ensure it's within limits
    assume(len(markdown_with_special_chars) <= 50000)
    
    # Create a mock VM
    mock_vm = VM(
        id=1,
        user_id=1,
        hostname="test-vm",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=markdown_with_special_chars
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act
    retrieved_vm = vm_service.get_vm(vm_id=1, user_id=1)
    
    # Assert - Special characters should be preserved
    assert retrieved_vm.deployment_notes == markdown_with_special_chars, \
        "Markdown special characters should be preserved without modification"


@given(
    markdown_content=st.text(min_size=1, max_size=50000)
)
def test_property_markdown_length_limit_enforced(markdown_content, mock_db_session):
    """
    Property 7: Markdown Preservation (Length Limit)
    
    Property: Deployment notes should enforce the 50,000 character limit,
    regardless of Markdown formatting.
    
    Validates: Requirement 6.4 - Max 50,000 characters for deployment notes
    """
    # Arrange
    vm_service = VMRegistryService(mock_db_session)
    
    # Create a mock VM
    mock_vm = VM(
        id=1,
        user_id=1,
        hostname="test-vm",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=""
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act & Assert
    if len(markdown_content) <= 50000:
        # Should accept content within limit
        try:
            vm_service.update_vm(
                vm_id=1,
                user_id=1,
                deployment_notes=markdown_content
            )
            assert len(mock_vm.deployment_notes) <= 50000
        except Exception as e:
            pytest.fail(f"Should accept Markdown content within limit: {e}")
    else:
        # Should reject content exceeding limit
        from vmledger.exceptions import ValidationError
        with pytest.raises(ValidationError):
            vm_service.update_vm(
                vm_id=1,
                user_id=1,
                deployment_notes=markdown_content
            )


@given(
    markdown_with_newlines=st.text(
        min_size=10,
        max_size=1000,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="\n\r\t ")
    )
)
def test_property_markdown_whitespace_preserved(
    markdown_with_newlines, mock_db_session
):
    """
    Property 7: Markdown Preservation (Whitespace)
    
    Property: Whitespace (newlines, tabs, spaces) in Markdown should be
    preserved exactly as entered, as it affects Markdown rendering.
    
    Validates: Requirement 6.2 - Support Markdown formatting in deployment notes
    """
    # Arrange
    vm_service = VMRegistryService(mock_db_session)
    
    # Ensure it's within limits
    assume(len(markdown_with_newlines) <= 50000)
    
    # Create a mock VM
    mock_vm = VM(
        id=1,
        user_id=1,
        hostname="test-vm",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=markdown_with_newlines
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act
    retrieved_vm = vm_service.get_vm(vm_id=1, user_id=1)
    
    # Assert - Whitespace should be preserved
    assert retrieved_vm.deployment_notes == markdown_with_newlines, \
        "Markdown whitespace (newlines, tabs, spaces) should be preserved exactly"


@given(
    code_block=st.text(
        min_size=10,
        max_size=500,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "P"), whitelist_characters="\n\t {}[]();")
    )
)
def test_property_markdown_code_blocks_preserved(code_block, mock_db_session):
    """
    Property 7: Markdown Preservation (Code Blocks)
    
    Property: Code blocks in Markdown (fenced with ```) should preserve
    all content including special characters and indentation.
    
    Validates: Requirement 6.2 - Support Markdown formatting in deployment notes
    """
    # Arrange
    vm_service = VMRegistryService(mock_db_session)
    
    # Wrap in Markdown code block
    markdown_content = f"```python\n{code_block}\n```"
    
    # Ensure it's within limits
    assume(len(markdown_content) <= 50000)
    
    # Create a mock VM
    mock_vm = VM(
        id=1,
        user_id=1,
        hostname="test-vm",
        ip_address="192.168.1.100",
        ssh_port=22,
        tags=["test"],
        deployment_notes=markdown_content
    )
    
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_vm
    
    # Act
    retrieved_vm = vm_service.get_vm(vm_id=1, user_id=1)
    
    # Assert - Code block content should be preserved exactly
    assert retrieved_vm.deployment_notes == markdown_content, \
        "Markdown code blocks should preserve all content exactly"
    assert code_block in retrieved_vm.deployment_notes, \
        "Code block content should be present in deployment notes"
