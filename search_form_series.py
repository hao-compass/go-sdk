"""Simple script to search for form series by name or ID."""
import logging

from shovel import task

from web.documents.models import db
from web.documents.models import documents_form_series

logger = logging.getLogger(__name__)


@task
def main(search_term=None):  # type: ignore
    """
    Search for form series by name.

    Args:
        search_term: Optional text to search in form series title

    Usage:
        python manage.py shovel search_form_series.main
        python manage.py shovel search_form_series.main RPA
    """
    print("=" * 80)
    print("FORM SERIES SEARCH")
    print("=" * 80)

    if search_term:
        print(f"\nSearching for: '{search_term}'")

    try:
        query = db.session.query(documents_form_series)
        
        if search_term:
            # Try both title search and exact ID match
            if search_term.isdigit():
                query = query.filter(
                    db.or_(
                        documents_form_series.c.title.ilike(f'%{search_term}%'),
                        documents_form_series.c.id == int(search_term)
                    )
                )
            else:
                query = query.filter(
                    documents_form_series.c.title.ilike(f'%{search_term}%')
                )
        
        query = query.order_by(documents_form_series.c.created_at.desc()).limit(50)
        results = query.all()
        
        print(f"\nFound {len(results)} form series:\n")
        print("-" * 80)
        
        for row in results:
            print(f"\nID: {row.id}")
            print(f"Title: {row.title}")
            print(f"Default Form ID: {row.default_form_id}")
            print(f"Created: {row.created_at}")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
