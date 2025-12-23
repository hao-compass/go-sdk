import json
import logging
from typing import Dict, List, Optional

from shovel import task

from helpers.protobufs.json_format import MessageToDict, Parse
from reform.config import reform_pb2
from web.documents.services import FillConfigService
from web.documents.services import FormSeriesService
from web.documents.services import FormService

logger = logging.getLogger(__name__)

RPA_FORM_SERIES_ID = '829'
OUTLINE_PATH_TEMPLATE = '/code/web/flows/handlers/app/rpa/outline{}.json'


def _load_outline_version(version: str) -> Optional[reform_pb2.FormOutline]:
    """Load an outline version from JSON file."""
    if version == '0':
        return reform_pb2.FormOutline()

    outline_file = OUTLINE_PATH_TEMPLATE.format(version)
    try:
        with open(outline_file, 'r') as f:
            outline_json = json.load(f)
        outline_string = json.dumps(outline_json)
        return Parse(outline_string, reform_pb2.FormOutline())
    except Exception as e:
        logger.error(f'Failed to load outline version {version}: {e}')
        return None


def _compare_outlines(current: reform_pb2.FormOutline, version: str, version_outline: reform_pb2.FormOutline) -> Dict:
    """Compare current outline with a specific version."""
    result = {
        'version': version,
        'matches': current == version_outline,
    }

    if current == version_outline:
        result['status'] = 'MATCH'
    else:
        result['status'] = 'NO_MATCH'
        # Count terms to give more details
        current_terms = len(current.terms) if current.terms else 0
        version_terms = len(version_outline.terms) if version_outline.terms else 0
        result['current_term_count'] = current_terms
        result['version_term_count'] = version_terms

    return result


def _get_outline_summary(outline: reform_pb2.FormOutline) -> Dict:
    """Get summary information about an outline."""
    if not outline or not outline.terms:
        return {
            'term_count': 0,
            'is_empty': True,
            'sample_terms': []
        }

    terms_count = len(outline.terms)
    sample_terms = []

    # Get first 5 terms' titles for identification
    for i, term in enumerate(outline.terms[:5]):
        if term.title:
            sample_terms.append({
                'number': term.number if term.number else str(i+1),
                'title': term.title,
                'kind': reform_pb2.FormOutline.Term.Kind.Name(term.kind)
            })

    # Get some specific identifiable terms from outline4
    identifiable_terms = []
    for term in outline.terms:
        if 'Broker' in term.title or 'broker' in term.title:
            identifiable_terms.append(term.title)
        if term.section and term.section.terms:
            for subterm in term.section.terms:
                if 'Broker' in subterm.title or '29' in subterm.title or 'other3' in str(subterm):
                    identifiable_terms.append(f"  └─ {subterm.title}")

    return {
        'term_count': terms_count,
        'is_empty': False,
        'sample_terms': sample_terms[:5],
        'identifiable_terms': identifiable_terms[:10]  # Limit to 10 for readability
    }


@task
def main(form_series_id: Optional[str] = None, form_id: Optional[str] = None) -> None:
    """
    Inspect the current RPA form outline deployment status.

    Args:
        form_series_id: Optional form series ID (defaults to RPA_FORM_SERIES_ID='829')
        form_id: Optional specific form ID (defaults to form_series.default_form_id)

    Usage:
        python manage.py shovel inspect_rpa_form_outline.main
        python manage.py shovel inspect_rpa_form_outline.main 829
        python manage.py shovel inspect_rpa_form_outline.main 829 <specific_form_id>
    """
    # Use default RPA form series if not specified
    form_series_id = form_series_id or RPA_FORM_SERIES_ID

    print("=" * 80)
    print("RPA FORM OUTLINE INSPECTION")
    print("=" * 80)

    # Get form series
    try:
        form_series = FormSeriesService().get_multi([form_series_id])[0]
        print(f"\n✓ Form Series ID: {form_series_id}")
        print(f"  Name: {form_series.name if hasattr(form_series, 'name') else 'N/A'}")
    except Exception as e:
        print(f"\n✗ ERROR: Could not load form series {form_series_id}: {e}")
        return

    # Get form
    form_id = form_id or form_series.default_form_id
    try:
        form = FormService().get_multi([form_id])[0]
        print(f"  Default Form ID: {form_id}")
        print(f"  Fill Config ID: {form.fill_config_id}")
    except Exception as e:
        print(f"\n✗ ERROR: Could not load form {form_id}: {e}")
        return

    # Get fill config
    try:
        fill_config = FillConfigService().get_multi([form.fill_config_id])[0]
    except Exception as e:
        print(f"\n✗ ERROR: Could not load fill_config {form.fill_config_id}: {e}")
        return

    # Analyze current outline
    print("\n" + "-" * 80)
    print("CURRENT OUTLINE IN DATABASE")
    print("-" * 80)

    try:
        current_outline = fill_config.form_outline
        current_summary = _get_outline_summary(current_outline)

        if current_summary['is_empty']:
            print("\n⚠️  WARNING: No outline data found in database!")
            print("   The form_outline field is empty or has no terms.")
        else:
            print(f"\n✓ Outline exists with {current_summary['term_count']} top-level terms")

            if current_summary['sample_terms']:
                print("\n  Sample terms (first 5):")
                for term in current_summary['sample_terms']:
                    print(f"    {term['number']}. {term['title']} ({term['kind']})")

            if current_summary['identifiable_terms']:
                print("\n  Key identifiable terms:")
                for term in current_summary['identifiable_terms']:
                    print(f"    • {term}")

        # Compare with available versions
        print("\n" + "-" * 80)
        print("VERSION COMPARISON")
        print("-" * 80)

        versions_to_check = ['1', '2', '3', '4']
        comparison_results = []

        for version in versions_to_check:
            version_outline = _load_outline_version(version)
            if version_outline is not None:
                result = _compare_outlines(current_outline, version, version_outline)
                comparison_results.append(result)

        # Display comparison results
        for result in comparison_results:
            version = result['version']
            status = result['status']

            if status == 'MATCH':
                print(f"\n✓ MATCH: Current outline matches outline{version}.json")
                print(f"  └─ This environment is running outline version {version}")
            else:
                print(f"\n✗ NO MATCH: outline{version}.json")
                if 'current_term_count' in result and 'version_term_count' in result:
                    print(f"  └─ Current: {result['current_term_count']} terms, Version {version}: {result['version_term_count']} terms")

        # Summary and recommendations
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        matched_version = None
        for result in comparison_results:
            if result['status'] == 'MATCH':
                matched_version = result['version']
                break

        if matched_version:
            print(f"\n✓ Current deployment: outline{matched_version}")
            latest_version = versions_to_check[-1]
            if matched_version != latest_version:
                print(f"\n⚠️  NOTE: Latest available version is outline{latest_version}")
                print(f"   To upgrade, run:")
                print(f"   python manage.py shovel update_rpa_form_outline.main {matched_version} {latest_version}")
            else:
                print(f"\n✓ Already running the latest version (outline{latest_version})")
        elif current_summary['is_empty']:
            print("\n⚠️  Current deployment: NO OUTLINE DATA (empty)")
            print(f"   To deploy outline4, run:")
            print(f"   python manage.py shovel update_rpa_form_outline.main 0 4")
        else:
            print("\n⚠️  Current deployment: UNKNOWN VERSION (custom or corrupted)")
            print(f"   Current outline has {current_summary['term_count']} terms but doesn't match any known version")
            print(f"   To force deploy outline4, run:")
            print(f"   python manage.py shovel update_rpa_form_outline.main 0 4")
            print(f"   WARNING: This will replace the current outline regardless of version")
    except Exception as e:
        print(f"\n✗ ERROR during inspection: {e}")

    print("\n" + "=" * 80)
