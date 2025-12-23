"""Simple script to search for form series by name or ID, filtered by CA state."""
import logging

from shovel import task
from sqlalchemy.dialects.postgresql import ARRAY

from web.documents.models import db
from web.documents.models import documents_form_series
from web.documents.services import FormSeriesService

logger = logging.getLogger(__name__)


@task
def main(search_term=None, skip_ca_filter=False):  # type: ignore
    """
    Search for form series by name.

    Args:
        search_term: Optional text to search in form series title
        skip_ca_filter: If True, search all states (default: False)

    Usage:
        python manage.py shovel search_form_series.main RPA
        python manage.py shovel search_form_series.main RPA True  # All states
    """
    print("=" * 80)
    if skip_ca_filter:
        print("FORM SERIES SEARCH (ALL STATES)")
    else:
        print("FORM SERIES SEARCH (CA STATE ONLY)")
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

        # Filter for CA in application code if needed
        if not skip_ca_filter:
            ca_results = []
            for row in results:
                tags = list(row.tags) if row.tags else []
                # Check if any tag starts with 'ca.' or equals 'CA'
                is_ca = any(
                    tag.lower().startswith('ca.') or tag.upper() == 'CA' 
                    for tag in tags
                )
                if is_ca:
                    ca_results.append(row)
            results = ca_results

        state_label = "form series" if skip_ca_filter else "CA form series"
        print(f"\nFound {len(results)} {state_label}" + (f" matching '{search_term}'" if search_term else ""))
        print("-" * 80)

        for row in results:
            # Just show raw database data without fetching protobufs
            # Tags are stored as array in the database
            tags = list(row.tags) if row.tags else []

            print(f"\nID: {row.id}")
            print(f"Title: {row.title}")
            print(f"Tags: {tags}")
            print(f"Default Form ID: {row.default_form_id}")
            print(f"Created: {row.created_at}")
            print(f"Deleted: {row.deleted_at if hasattr(row, 'deleted_at') else 'N/A'}")

        print("\n" + "=" * 80)
        print(f"Total: {len(results)} {state_label} found")
        print("=" * 80)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
