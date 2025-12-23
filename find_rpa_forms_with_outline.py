import json
import logging

from shovel import task

from helpers.protobufs.json_format import MessageToDict
from reform.config import reform_pb2
from web.documents.models import documents_forms
from web.documents.services import FillConfigService
from web.documents.services import FormSeriesService
from web.documents.services import FormService

logger = logging.getLogger(__name__)

RPA_FORM_SERIES_ID = '829'


@task
def main(form_series_id=None):  # type: ignore
    """
    Find all forms in the RPA series and check which ones have outline data.

    Args:
        form_series_id: Optional form series ID (defaults to '829' for RPA)

    Usage:
        python manage.py shovel find_rpa_forms_with_outline.main
        python manage.py shovel find_rpa_forms_with_outline.main 829
    """
    form_series_id = form_series_id or RPA_FORM_SERIES_ID

    print("=" * 80)
    print("RPA FORMS WITH OUTLINE SEARCH")
    print("=" * 80)

    # Get form series
    try:
        form_series = FormSeriesService().get_multi([form_series_id])[0]
        print(f"\n✓ Form Series ID: {form_series_id}")
        print(f"  Name: {form_series.name if hasattr(form_series, 'name') else 'N/A'}")
        print(f"  Default Form ID: {form_series.default_form_id}")
    except Exception as e:
        print(f"\n✗ ERROR: Could not load form series {form_series_id}: {e}")
        return

    # Find all forms in this series
    print("\n" + "-" * 80)
    print("SEARCHING ALL FORMS IN SERIES")
    print("-" * 80)

    try:
        # Query all forms for this series
        from web.documents.models import db
        query = db.session.query(documents_forms).filter(
            documents_forms.c.form_series_id == form_series_id
        ).order_by(documents_forms.c.created_at.desc())

        all_forms = query.all()
        print(f"\n✓ Found {len(all_forms)} total forms in series {form_series_id}")

    except Exception as e:
        print(f"\n✗ ERROR querying forms: {e}")
        return

    # Check each form's fill_config for outline data
    print("\n" + "-" * 80)
    print("CHECKING FILL CONFIGS FOR OUTLINE DATA")
    print("-" * 80)

    forms_with_outline = []
    forms_without_outline = []

    for form_row in all_forms:
        form_id = form_row.id
        fill_config_id = form_row.fill_config_id

        try:
            form = FormService().get_multi([form_id])[0]
            fill_config = FillConfigService().get_multi([fill_config_id])[0]

            outline = fill_config.form_outline
            has_outline = outline and outline.terms and len(outline.terms) > 0

            form_info = {
                'form_id': form_id,
                'fill_config_id': fill_config_id,
                'created_at': form_row.created_at,
                'is_default': form_id == form_series.default_form_id,
                'term_count': len(outline.terms) if has_outline else 0,
                'state': form.state if hasattr(form, 'state') else 'UNKNOWN'
            }

            if has_outline:
                forms_with_outline.append(form_info)

                # Get sample terms for identification
                sample_terms = []
                for i, term in enumerate(outline.terms[:3]):
                    if term.title:
                        sample_terms.append(term.title)
                form_info['sample_terms'] = sample_terms
            else:
                forms_without_outline.append(form_info)

        except Exception as e:
            logger.error(f"Error processing form {form_id}: {e}")
            continue

    # Display results
    if forms_with_outline:
        print(f"\n✓ FORMS WITH OUTLINE DATA ({len(forms_with_outline)}):")
        print("-" * 80)
        for info in forms_with_outline:
            print(f"\n  Form ID: {info['form_id']}")
            print(f"  Fill Config ID: {info['fill_config_id']}")
            print(f"  Default: {'YES' if info['is_default'] else 'No'}")
            print(f"  Terms: {info['term_count']}")
            print(f"  Created: {info['created_at']}")
            if 'sample_terms' in info and info['sample_terms']:
                print(f"  Sample Terms:")
                for term in info['sample_terms']:
                    print(f"    • {term}")
    else:
        print("\n⚠️  NO FORMS FOUND WITH OUTLINE DATA")

    print("\n" + "-" * 80)
    if forms_without_outline:
        print(f"✗ FORMS WITHOUT OUTLINE DATA ({len(forms_without_outline)}):")
        print("-" * 80)
        for info in forms_without_outline[:5]:  # Show first 5
            print(f"\n  Form ID: {info['form_id']}")
            print(f"  Default: {'YES' if info['is_default'] else 'No'}")
            print(f"  Created: {info['created_at']}")

        if len(forms_without_outline) > 5:
            print(f"\n  ... and {len(forms_without_outline) - 5} more")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nTotal forms: {len(all_forms)}")
    print(f"Forms WITH outline: {len(forms_with_outline)}")
    print(f"Forms WITHOUT outline: {len(forms_without_outline)}")

    if forms_with_outline:
        print("\n✓ Outline data found in some forms")
        print("\nTo set a specific form as default:")
        for info in forms_with_outline:
            if not info['is_default']:
                print(f"  # Use form {info['form_id']} (has {info['term_count']} terms)")
                print(f"  # You may need to update form_series.default_form_id")
    else:
        print("\n⚠️  NO outline data found in ANY forms")
        print("\nTo deploy outline4 to the default form:")
        print(f"  python manage.py shovel update_rpa_form_outline.main 0 4")

    print("\n" + "=" * 80)
