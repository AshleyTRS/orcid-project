"""
Migration: Link contributors to ORCID profiles.

Builds a mapping from normalized researcher names (given_names + family_names
of each stored profile) to ORCID iDs and assigns the matching ORCID iD to
contributors that do not have one yet.

Both sides of the comparison use src.works.names.normalize_person_name, the
normalization applied to contributor names at harvest time. Names shared by
two or more profiles are ambiguous and are not used for linking. A contributor
that already carries an ORCID iD (for example one supplied by ORCID itself) is
never changed.
"""
import logging
from collections import defaultdict
from typing import Dict, Iterable, List, Set, Tuple

from pymongo import UpdateOne

from src.works.names import normalize_person_name

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BULK_BATCH_SIZE = 1000


def normalize_name(name: str) -> str:
    """Normalize a name for matching (see src.works.names.normalize_person_name)."""
    return normalize_person_name(name)


def build_name_index(profiles: Iterable[Dict]) -> Tuple[Dict[str, str], Set[str]]:
    """
    Map normalized profile names to ORCID iDs.

    Returns:
        (index, ambiguous): index maps each name held by exactly one profile to
        its ORCID iD; ambiguous holds names shared by two or more profiles,
        which are excluded from the index.
    """
    owners = defaultdict(set)
    for profile in profiles:
        given = (profile.get("given_names") or "").strip()
        family = (profile.get("family_names") or "").strip()
        normalized = normalize_person_name(f"{given} {family}")
        if normalized and profile.get("orcid_id"):
            owners[normalized].add(profile["orcid_id"])

    index = {name: next(iter(ids)) for name, ids in owners.items() if len(ids) == 1}
    ambiguous = {name for name, ids in owners.items() if len(ids) > 1}
    return index, ambiguous


def plan_contributor_links(works: Iterable[Dict], name_index: Dict[str, str]) -> Tuple[Dict, Dict]:
    """
    Decide which contributors to link, without writing anything.

    Returns:
        (links, stats): links maps a work _id to {contributor position: ORCID iD};
        stats counts contributors examined, already linked and newly matched.
    """
    links = defaultdict(dict)
    stats = {"total_contributors": 0, "already_linked": 0, "matched_contributors": 0}

    for work in works:
        for position, contributor in enumerate(work.get("contributors") or []):
            if not isinstance(contributor, dict):
                continue
            stats["total_contributors"] += 1
            if contributor.get("orcid_id"):
                stats["already_linked"] += 1
                continue
            name = contributor.get("normalized_name") or contributor.get("credit_name")
            orcid_id = name_index.get(normalize_person_name(name))
            if orcid_id:
                links[work["_id"]][position] = orcid_id
                stats["matched_contributors"] += 1

    return dict(links), stats


def link_contributors(works_collection, orcids_collection):
    """
    Link contributors to ORCID profiles by matching normalized names.

    Args:
        works_collection: MongoDB works collection
        orcids_collection: MongoDB orcids collection

    Returns:
        Status dict with the number of works updated, contributors examined,
        contributors already linked, contributors newly linked and ambiguous names.
    """
    logger.info("Starting contributor linking migration...")

    try:
        profiles = orcids_collection.find({}, {"orcid_id": 1, "given_names": 1, "family_names": 1})
        name_index, ambiguous = build_name_index(profiles)
        logger.info(f"Built mapping for {len(name_index)} ORCID names ({len(ambiguous)} ambiguous names skipped)")

        works = list(works_collection.find(
            {"contributors": {"$exists": True, "$type": "array"}},
            {"_id": 1, "contributors": 1}
        ))
        logger.info(f"Processing {len(works)} works with contributors")

        links, stats = plan_contributor_links(works, name_index)

        updates: List[UpdateOne] = [
            UpdateOne(
                {"_id": work_id},
                {"$set": {f"contributors.{position}.orcid_id": orcid_id for position, orcid_id in positions.items()}}
            )
            for work_id, positions in links.items()
        ]
        for start in range(0, len(updates), BULK_BATCH_SIZE):
            works_collection.bulk_write(updates[start:start + BULK_BATCH_SIZE], ordered=False)

        logger.info(
            f"Contributor linking completed. Works updated: {len(updates)}, "
            f"Total contributors: {stats['total_contributors']}, Already linked: {stats['already_linked']}, "
            f"Newly linked: {stats['matched_contributors']}"
        )
        return {
            "status": "success",
            "works_updated": len(updates),
            "total_contributors": stats["total_contributors"],
            "already_linked": stats["already_linked"],
            "matched_contributors": stats["matched_contributors"],
            "ambiguous_names": len(ambiguous),
            "errors": 0
        }

    except Exception as e:
        logger.error(f"Contributor linking migration failed: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


if __name__ == "__main__":
    from src.db.MongoConnection import MongoConnection
    import os
    from dotenv import load_dotenv

    load_dotenv()
    mongo = MongoConnection(os.getenv("MONGO_CONN"), os.getenv("DB_NAME"))
    result = link_contributors(mongo.works(), mongo.orcids())
    print(result)
    mongo.close()
