"""Clean up old empty Milvus collections.

WARNING: This script drops ALL Milvus collections in the connected instance.
Use only in development / test environments. Not safe for production.

Usage:
    python scripts/cleanup_milvus.py            # preview only (dry-run)
    python scripts/cleanup_milvus.py --force    # actually drop collections
"""
import argparse
import sys

sys.path.insert(0, ".")

from pymilvus import connections, utility


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drop all Milvus collections (development use only)."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Actually drop collections. Without this flag, runs in dry-run mode.",
    )
    args = parser.parse_args()

    if not args.force:
        print("[DRY-RUN] No collections will be deleted.")
        print("          Pass --force to actually drop collections.\n")

    host = "localhost"
    port = "19530"
    connections.connect(host=host, port=port)
    cols = utility.list_collections()
    print(f"Found {len(cols)} collections: {cols}\n")

    if not cols:
        print("Nothing to clean up.")
        connections.disconnect("default")
        return

    for c in cols:
        if args.force:
            try:
                utility.drop_collection(c)
                print(f"  [OK] Dropped: {c}")
            except Exception as e:
                print(f"  [FAIL] {c}: {e}")
        else:
            print(f"  [dry-run] Would drop: {c}")

    remaining = utility.list_collections()
    print(f"\nRemaining: {remaining}")

    if args.force:
        print("Done - collections dropped.")
    else:
        print("Done - add --force to actually delete.")

    connections.disconnect("default")


if __name__ == "__main__":
    main()
