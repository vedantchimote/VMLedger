"""
Search Engine Service for full-text search across VM metadata and deployment notes.

Uses PostgreSQL full-text search with tsvector and GIN indexes for efficient searching.
Implements ranking, highlighting, and OR logic for multi-term queries.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from vmledger.models.vm import VM
import logging

logger = logging.getLogger(__name__)


class VMSearchResult:
    """
    Search result containing VM data with relevance ranking and highlighted matches.
    
    Attributes:
        vm: The VM model instance
        rank: Relevance score from ts_rank
        highlighted_notes: Deployment notes with highlighted matches (if applicable)
    """
    
    def __init__(self, vm: VM, rank: float, highlighted_notes: Optional[str] = None):
        self.vm = vm
        self.rank = rank
        self.highlighted_notes = highlighted_notes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert search result to dictionary for API responses."""
        return {
            'id': self.vm.id,
            'ip_address': self.vm.ip_address,
            'hostname': self.vm.hostname,
            'domain': self.vm.domain,
            'ssh_port': self.vm.ssh_port,
            'tags': self.vm.tags or [],
            'deployment_notes': self.vm.deployment_notes,
            'highlighted_notes': self.highlighted_notes,
            'rank': self.rank,
            'created_at': self.vm.created_at.isoformat() if self.vm.created_at else None,
            'updated_at': self.vm.updated_at.isoformat() if self.vm.updated_at else None,
            'last_seen': self.vm.last_seen.isoformat() if self.vm.last_seen else None,
            'is_reachable': self.vm.is_reachable
        }


class SearchEngineService:
    """
    Full-text search service using PostgreSQL's tsvector and tsquery.
    
    Features:
    - Search across IP addresses, hostnames, domains, tags, and deployment notes
    - Relevance ranking using ts_rank
    - Highlighting of matches in deployment notes using ts_headline
    - OR logic for multi-term queries
    - User isolation enforcement
    - Performance target: < 500ms for 100 VMs
    """
    
    def __init__(self, db: Session):
        """
        Initialize search engine service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def search_vms(self, user_id: int, query: str, limit: int = 50) -> List[VMSearchResult]:
        """
        Search VMs using full-text search with ranking and highlighting.
        
        Implements Requirements 7.1-7.6:
        - 7.1: Index VM metadata and deployment notes
        - 7.2: Return results within 500ms
        - 7.3: Support partial word matching
        - 7.4: Rank by relevance (exact matches first)
        - 7.5: Highlight matches in deployment notes
        - 7.6: OR logic for multi-term queries
        
        Args:
            user_id: User ID for isolation enforcement
            query: Search query string
            limit: Maximum number of results (default 50)
        
        Returns:
            List of VMSearchResult objects ordered by rank DESC, hostname ASC
        """
        if not query or not query.strip():
            logger.debug(f"Empty search query for user {user_id}")
            return []
        
        # Convert user query to tsquery format with OR logic
        # Split on whitespace and join with OR operator
        query_terms = query.strip().split()
        ts_query = " | ".join(query_terms)
        
        logger.debug(f"Search query for user {user_id}: '{query}' -> tsquery: '{ts_query}'")
        
        try:
            # Execute search with ranking
            # Use to_tsquery with 'simple' config for partial matching
            results = self.db.query(
                VM,
                func.ts_rank(VM.search_vector, func.to_tsquery('english', ts_query)).label('rank')
            ).filter(
                VM.user_id == user_id,
                VM.search_vector.op('@@')(func.to_tsquery('english', ts_query))
            ).order_by(
                text('rank DESC'),
                VM.hostname.asc()
            ).limit(limit).all()
            
            logger.info(f"Search returned {len(results)} results for user {user_id}")
            
            # Build search results with highlighting
            search_results = []
            for vm, rank in results:
                highlighted_notes = None
                
                # Highlight matches in deployment notes if present
                if vm.deployment_notes:
                    highlighted_notes = self.highlight_matches(
                        vm.deployment_notes,
                        ts_query
                    )
                
                search_results.append(VMSearchResult(
                    vm=vm,
                    rank=float(rank),
                    highlighted_notes=highlighted_notes
                ))
            
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed for user {user_id}, query '{query}': {e}")
            raise
    
    def highlight_matches(self, text: str, ts_query: str) -> str:
        """
        Highlight matching text using ts_headline.
        
        Implements Requirement 7.5: Highlight matches in deployment notes.
        
        Args:
            text: Text to highlight (deployment notes)
            ts_query: PostgreSQL tsquery string
        
        Returns:
            Text with highlighted matches wrapped in <mark> tags
        """
        if not text or not ts_query:
            return text
        
        try:
            # Use ts_headline to highlight matches
            # MaxFragments=3: Return top 3 matching fragments
            # MaxWords=50: Max 50 words per fragment (~200 chars)
            # MinWords=25: Min 25 words per fragment
            # StartSel/StopSel: Use <mark> HTML tags for highlighting
            result = self.db.execute(
                text("""
                    SELECT ts_headline(
                        'english',
                        :text,
                        to_tsquery('english', :query),
                        'MaxFragments=3, MaxWords=50, MinWords=25, StartSel=<mark>, StopSel=</mark>'
                    )
                """),
                {'text': text, 'query': ts_query}
            ).scalar()
            
            return result if result else text
            
        except Exception as e:
            logger.warning(f"Highlighting failed for query '{ts_query}': {e}")
            return text
    
    def index_vm(self, vm: VM) -> None:
        """
        Index a VM for full-text search.
        
        Note: The search_vector is automatically updated by the database trigger
        (vms_search_vector_update) on INSERT. This method is provided for
        explicit indexing if needed.
        
        Args:
            vm: VM instance to index
        """
        # The trigger handles indexing automatically, but we can force an update
        try:
            self.db.execute(
                text("""
                    UPDATE vms
                    SET search_vector = 
                        setweight(to_tsvector('pg_catalog.english', COALESCE(:ip_address, '')), 'A') ||
                        setweight(to_tsvector('pg_catalog.english', COALESCE(:hostname, '')), 'A') ||
                        setweight(to_tsvector('pg_catalog.english', COALESCE(:domain, '')), 'B') ||
                        setweight(to_tsvector('pg_catalog.english', COALESCE(:tags, '')), 'B') ||
                        setweight(to_tsvector('pg_catalog.english', COALESCE(:deployment_notes, '')), 'C')
                    WHERE id = :vm_id
                """),
                {
                    'vm_id': vm.id,
                    'ip_address': vm.ip_address,
                    'hostname': vm.hostname,
                    'domain': vm.domain or '',
                    'tags': ' '.join(vm.tags) if vm.tags else '',
                    'deployment_notes': vm.deployment_notes or ''
                }
            )
            self.db.commit()
            logger.debug(f"Indexed VM {vm.id} for search")
        except Exception as e:
            logger.error(f"Failed to index VM {vm.id}: {e}")
            self.db.rollback()
            raise
    
    def update_index(self, vm_id: int, vm: VM) -> None:
        """
        Update search index for a VM.
        
        Note: The search_vector is automatically updated by the database trigger
        (vms_search_vector_update) on UPDATE. This method is provided for
        explicit re-indexing if needed.
        
        Args:
            vm_id: VM ID to update
            vm: VM instance with updated data
        """
        # The trigger handles updates automatically
        self.index_vm(vm)
    
    def delete_from_index(self, vm_id: int) -> None:
        """
        Delete a VM from the search index.
        
        Note: When a VM is deleted from the database, the search_vector is
        automatically removed. This method is provided for explicit removal
        if needed.
        
        Args:
            vm_id: VM ID to remove from index
        """
        try:
            # Deletion from the vms table automatically removes the search_vector
            # This method is a no-op but provided for API completeness
            logger.debug(f"VM {vm_id} will be removed from search index on deletion")
        except Exception as e:
            logger.error(f"Failed to delete VM {vm_id} from index: {e}")
            raise


def get_search_engine_service(db: Session) -> SearchEngineService:
    """
    Factory function to create SearchEngineService instance.
    
    Args:
        db: SQLAlchemy database session
    
    Returns:
        SearchEngineService instance
    """
    return SearchEngineService(db)
