"""
Check if a form (by UUID) has form_outline data in its fill_config.

This script mimics the API flow:
1. Find form by UUID
2. Resolve fill_config
3. Check if form_outline exists
4. Display the outline structure

Does NOT require transaction document ID (no enrichment step).
"""
import json
import logging

from shovel import task

from helpers.protobufs.utils import pb_to_dict_client
from web.database import resolver
from web.documents.services import FormService
import services

logger = logging.getLogger(__name__)


@task
def main(form_uuid):  # type: ignore
    """
    Check if a form has form_outline in its fill_config.

    This follows the same flow as the API endpoint:
    GET /api/forms/{form_uuid}/fill_config

    Args:
        form_uuid: Form UUID (e.g., "abc123-def456-...")

    Usage:
        ./devtool/dev-glide webapp shovel check_form_outline_by_uuid.main <form_uuid>

    Example:
        ./devtool/dev-glide webapp shovel check_form_outline_by_uuid.main "abc123-def456-ghi789"
    """
    print("=" * 80)
    print("FORM OUTLINE CHECK BY UUID")
    print("=" * 80)

    try:
        # Step 1: Get form by UUID (same as API)
        print(f"\n[Step 1] Finding form by UUID: {form_uuid}")
        print("-" * 80)

        form = FormService().get_by_uuid(uuid=form_uuid)

        print(f"✓ Form found:")
        print(f"  Form ID: {form.id}")
        print(f"  Title: {form.title}")
        print(f"  Version: {form.version}")
        print(f"  Series ID: {form.series_id}")
        print(f"  Fill Config ID: {form.fill_config_id}")
        print(f"  UUID: {form_uuid}")

        # Step 2: Resolve fill_config (same as API)
        print(f"\n[Step 2] Resolving fill_config...")
        print("-" * 80)

        resolver.resolve([form], ['fill_config'])

        if not form.HasField('fill_config'):
            print("✗ ERROR: Form has no fill_config!")
            print("  This form may not have a fill configuration set up.")
            return

        print(f"✓ Fill config resolved:")
        print(f"  Fill Config ID: {form.fill_config.id}")

        # Check if form_outline exists in the protobuf
        has_outline_field = form.fill_config.HasField('form_outline')
        term_count = len(form.fill_config.form_outline.terms) if has_outline_field else 0

        print(f"  Has form_outline field: {has_outline_field}")
        if has_outline_field:
            print(f"  Form outline terms count: {term_count}")

        # Step 3: Convert to dict (same as API) - this is what gets sent to client
        print(f"\n[Step 3] Converting to client dict (JSON serialization)...")
        print("-" * 80)

        result_dict = pb_to_dict_client(form.fill_config)

        # Step 4: Check what's in the response
        print(f"\n[Step 4] Analyzing API response...")
        print("=" * 80)

        has_outline_in_dict = 'formOutline' in result_dict
        outline_data = result_dict.get('formOutline', {}) if has_outline_in_dict else {}
        dict_term_count = len(outline_data.get('terms', [])) if has_outline_in_dict else 0

        print(f"\n{'✓' if has_outline_in_dict else '✗'} 'formOutline' in API response: {has_outline_in_dict}")

        if has_outline_in_dict:
            print(f"{'✓' if dict_term_count > 0 else '✗'} Has outline data: {dict_term_count > 0}")
            print(f"  Terms in response: {dict_term_count}")

            if dict_term_count > 0:
                print("\n" + "=" * 80)
                print("✓ SUCCESS: FORM OUTLINE IS PRESENT")
                print("=" * 80)
                print(f"\nForm '{form.title}' has {dict_term_count} top-level outline terms.")
                print("\nTop-level sections:")

                for i, term in enumerate(outline_data.get('terms', [])[:10], 1):
                    term_kind = term.get('kind', 'UNKNOWN')
                    term_title = term.get('title', 'Untitled')
                    term_number = term.get('number', '')

                    # Count nested terms
                    nested_count = 0
                    if 'section' in term and 'terms' in term['section']:
                        nested_count = len(term['section']['terms'])
                    elif 'combo' in term and 'terms' in term['combo']:
                        nested_count = len(term['combo']['terms'])

                    nested_info = f" ({nested_count} sub-terms)" if nested_count > 0 else ""
                    print(f"  {term_number}. {term_title} [{term_kind}]{nested_info}")

                if dict_term_count > 10:
                    print(f"  ... and {dict_term_count - 10} more terms")

                # Show sample field IDs
                first_term = outline_data.get('terms', [{}])[0]
                if 'fieldIds' in first_term:
                    print(f"\nSample field IDs from first term:")
                    for key, value in list(first_term['fieldIds'].items())[:3]:
                        print(f"  '{key}': '{value}'")

                print("\n" + "-" * 80)
                print("NEXT STEPS:")
                print("-" * 80)
                print("✓ Backend is correctly returning form_outline")
                print("✓ Check if LaunchDarkly 'form_outline' flag is enabled")
                print("✓ Check frontend FormOutline component rendering")

            else:
                print("\n" + "=" * 80)
                print("✗ ISSUE: formOutline field exists but is empty")
                print("=" * 80)
                print("\nPossible reasons:")
                print("  1. Form outline was never configured for this form")
                print("  2. Outline data was cleared/deleted")
                print("  3. Fill config was created before outline feature existed")

        else:
            print("\n" + "=" * 80)
            print("✗ ISSUE: formOutline NOT in API response")
            print("=" * 80)

            if has_outline_field and term_count > 0:
                print("\n⚠️  CRITICAL: Outline exists in protobuf but NOT in JSON!")
                print(f"   Protobuf has {term_count} terms")
                print(f"   JSON dict has NO formOutline field")
                print("\nThis suggests pb_to_dict_client is filtering out the field.")
                print("Possible reasons:")
                print("  1. The field is considered 'default' and excluded")
                print("  2. Serialization options are removing empty nested fields")
            else:
                print("\nForm outline is not configured for this form.")
                print("The fill_config does not contain outline data.")

        # Show top-level fields in response
        print(f"\n" + "=" * 80)
        print(f"TOP-LEVEL FIELDS IN API RESPONSE")
        print("=" * 80)
        print(f"\nTotal fields: {len(result_dict.keys())}")
        print("\nField list:")
        for i, key in enumerate(sorted(result_dict.keys()), 1):
            value = result_dict[key]
            value_type = type(value).__name__

            # Provide meaningful summary
            if isinstance(value, list):
                summary = f"list with {len(value)} items"
            elif isinstance(value, dict):
                summary = f"dict with {len(value)} keys"
            elif isinstance(value, str):
                summary = f"'{value[:50]}...'" if len(value) > 50 else f"'{value}'"
            else:
                summary = str(value)

            print(f"  {i:2d}. {key:<30} ({value_type}): {summary}")

        # Optional: Export full JSON
        if dict_term_count > 0:
            print(f"\n" + "=" * 80)
            print("FORM OUTLINE JSON STRUCTURE")
            print("=" * 80)
            outline_json = json.dumps(outline_data, indent=2)

            if len(outline_json) > 3000:
                print(outline_json[:3000])
                print(f"\n... (truncated, total: {len(outline_json)} chars)")
                print(f"\nTo see full outline, modify the script or export to file")
            else:
                print(outline_json)

    except services.NotFoundError as e:
        print(f"\n✗ ERROR: Form not found!")
        print(f"  UUID: {form_uuid}")
        print(f"  Message: {e}")
        print("\nPlease check:")
        print("  1. UUID is correct (no typos)")
        print("  2. Form exists in the database")
        print("  3. You have access to this form")

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()


