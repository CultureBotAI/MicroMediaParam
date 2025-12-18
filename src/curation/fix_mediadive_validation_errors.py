#!/usr/bin/env python3
"""
Fix validation errors in mediadive_solutions_additions.yaml by adding missing 'names' and 'description' fields.
"""

import yaml
from pathlib import Path


def fix_mediadive_yaml(yaml_path: str):
    """Add missing 'names' and 'description' fields to all ingredients."""

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    if 'ingredients' not in data:
        print("No 'ingredients' section found")
        return

    fixed_count = 0
    for key, ingredient in data['ingredients'].items():
        modified = False

        # Add 'names' field if missing (use common_name and synonyms)
        if 'names' not in ingredient:
            names = []
            if 'common_name' in ingredient:
                names.append(ingredient['common_name'])
            if 'synonyms' in ingredient:
                names.extend(ingredient['synonyms'])
            ingredient['names'] = names if names else [ingredient.get('common_name', key.replace('_', ' ').title())]
            modified = True

        # Add 'description' field if missing
        if 'description' not in ingredient:
            # Generate description from available info
            sol_id = ingredient.get('mediadive_solution_id', 'unknown')
            usage = ingredient.get('usage_count', 0)
            volume_note = ingredient.get('note', '')

            # Count components
            component_count = 0
            for section in ['trace_elements', 'vitamins', 'other_compounds']:
                if section in ingredient:
                    component_count += len(ingredient[section])

            desc_parts = [f"DSMZ MediaDive solution {sol_id}"]
            if component_count > 0:
                desc_parts.append(f"containing {component_count} chemical components")
            if usage > 0:
                desc_parts.append(f"used in {usage} media formulations")
            if volume_note:
                desc_parts.append(volume_note)

            ingredient['description'] = '. '.join(desc_parts) + '.'
            modified = True

        if modified:
            fixed_count += 1

    # Write back to file
    with open(yaml_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"✅ Fixed {fixed_count} ingredients in {yaml_path}")
    print(f"   Total ingredients: {len(data['ingredients'])}")


if __name__ == '__main__':
    yaml_file = Path(__file__).parent.parent.parent / 'data' / 'curated' / 'complex_ingredients' / 'mediadive_solutions_additions.yaml'

    print(f"Fixing validation errors in: {yaml_file}")
    fix_mediadive_yaml(str(yaml_file))

    print("\nRe-validating...")
    import subprocess
    result = subprocess.run(
        ['python3', 'src/curation/evidence_validator.py', '--yaml', str(yaml_file)],
        capture_output=True,
        text=True
    )

    # Show validation summary
    for line in result.stdout.split('\n'):
        if 'VALIDATION SUMMARY' in line or 'Errors:' in line or 'Warnings:' in line or 'validation checks' in line:
            print(line)
