"""
Person-name normalization shared by the works harvester and contributor linking.

Both sides of a name comparison must be normalized by the same function:
contributor names are normalized when works are harvested
(contributors[].normalized_name), and researcher profile names are normalized
when contributors are linked to profiles (src/data_migration/link_contributors.py).
"""
import re
import unicodedata


def normalize_person_name(name: str) -> str:
    """
    Reduce a person's name to a comparable form.

    Accents are removed, the name is lower-cased, hyphens, commas and dashes
    become spaces, apostrophes are removed, any other character that is not a
    letter or space is dropped, and whitespace is collapsed.

    Example: "García-López, María José" -> "garcia lopez maria jose"
    """
    if not name:
        return ""

    # Normalize unicode (accents -> ascii)
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))

    # Lowercase
    name = name.lower()

    # Replace common separators with space
    name = re.sub(r"[-,–—]", " ", name)

    # Remove apostrophes (including unicode variants)
    name = re.sub(r"[’'`]", "", name)

    # Remove any remaining non-letter characters
    name = re.sub(r"[^a-z\s]", "", name)

    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name)

    return name.strip()
