#!/usr/bin/env python3
"""Database migration script for AI Co-Scientist.

This script creates all required tables in PostgreSQL by executing
the schema.sql file. Run this before using PostgreSQL storage.

Usage:
    # Using default settings from .env
    python scripts/migrate_db.py

    # Or specify database URL directly
    python scripts/migrate_db.py --database-url postgresql://user:pass@host:5432/db

    # Drop existing tables first (WARNING: destroys data)
    python scripts/migrate_db.py --drop-first

    # Verify tables exist
    python scripts/migrate_db.py --verify-only
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg is required. Install with: pip install asyncpg")
    sys.exit(1)


async def get_connection(database_url: str) -> asyncpg.Connection:
    """Create database connection."""
    print(f"Connecting to database: {database_url.split('@')[-1]}")
    return await asyncpg.connect(database_url)


async def read_schema() -> str:
    """Read the schema.sql file."""
    schema_path = project_root / "src" / "storage" / "schema.sql"
    if not schema_path.exists():
        print(f"ERROR: Schema file not found: {schema_path}")
        sys.exit(1)

    with open(schema_path, "r") as f:
        return f.read()


async def drop_tables(conn: asyncpg.Connection) -> None:
    """Drop all tables (in correct order for foreign keys)."""
    print("Dropping existing tables...")

    tables = [
        "chat_messages",
        "scientist_feedback",
        "context_memory",
        "system_statistics",
        "agent_tasks",
        "research_contacts",
        "research_directions",
        "research_overviews",
        "meta_reviews",
        "hypothesis_clusters",
        "proximity_edges",
        "proximity_graphs",
        "tournament_states",
        "tournament_matches",
        "reviews",
        "hypotheses",
        "research_plan_configurations",
        "research_goals",
    ]

    for table in tables:
        try:
            await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            print(f"  Dropped: {table}")
        except Exception as e:
            print(f"  Warning: Could not drop {table}: {e}")

    # Drop the trigger function
    await conn.execute("DROP FUNCTION IF EXISTS update_updated_at_column CASCADE")
    print("  Dropped: update_updated_at_column function")

    # Drop views
    views = ["top_hypotheses", "hypothesis_win_rates", "pending_tasks"]
    for view in views:
        try:
            await conn.execute(f"DROP VIEW IF EXISTS {view}")
            print(f"  Dropped view: {view}")
        except Exception as e:
            pass


async def run_migration(conn: asyncpg.Connection, schema_sql: str) -> None:
    """Execute schema SQL to create tables."""
    print("Creating tables...")

    # Split schema into individual statements
    # Note: This simple approach works for our schema, but complex schemas
    # might need proper SQL parsing
    statements = []
    current_statement = []

    for line in schema_sql.split("\n"):
        # Skip comments and empty lines for splitting purposes
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            current_statement.append(line)
            continue

        current_statement.append(line)

        # Check if statement ends with semicolon (not in a function body)
        if stripped.endswith(";") and "$$" not in "".join(current_statement):
            statements.append("\n".join(current_statement))
            current_statement = []
        elif stripped == "$$ LANGUAGE plpgsql;":
            statements.append("\n".join(current_statement))
            current_statement = []

    # Add any remaining content
    if current_statement:
        remaining = "\n".join(current_statement).strip()
        if remaining and not remaining.startswith("--"):
            statements.append(remaining)

    # Execute statements
    for i, statement in enumerate(statements):
        statement = statement.strip()
        if not statement or statement.startswith("--"):
            continue

        try:
            await conn.execute(statement)
        except Exception as e:
            # Extract first non-comment line for context
            first_line = ""
            for line in statement.split("\n"):
                if line.strip() and not line.strip().startswith("--"):
                    first_line = line.strip()[:60]
                    break
            print(f"  Warning on statement {i + 1} ({first_line}...): {e}")

    print("Migration complete!")


async def verify_tables(conn: asyncpg.Connection) -> bool:
    """Verify that all expected tables exist."""
    print("Verifying tables...")

    expected_tables = [
        "research_goals",
        "hypotheses",
        "reviews",
        "tournament_matches",
        "tournament_states",
        "proximity_edges",
        "hypothesis_clusters",
        "proximity_graphs",
        "meta_reviews",
        "research_directions",
        "research_contacts",
        "research_overviews",
        "agent_tasks",
        "system_statistics",
        "context_memory",
        "scientist_feedback",
        "chat_messages",
        "research_plan_configurations",
    ]

    # Query existing tables
    rows = await conn.fetch(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        """
    )
    existing = {row["table_name"] for row in rows}

    all_present = True
    for table in expected_tables:
        if table in existing:
            print(f"  ✓ {table}")
        else:
            print(f"  ✗ {table} (MISSING)")
            all_present = False

    # Check views
    expected_views = ["top_hypotheses", "hypothesis_win_rates", "pending_tasks"]
    view_rows = await conn.fetch(
        """
        SELECT table_name FROM information_schema.views
        WHERE table_schema = 'public'
        """
    )
    existing_views = {row["table_name"] for row in view_rows}

    print("\nVerifying views...")
    for view in expected_views:
        if view in existing_views:
            print(f"  ✓ {view}")
        else:
            print(f"  ✗ {view} (MISSING)")
            all_present = False

    return all_present


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database migration for AI Co-Scientist"
    )
    parser.add_argument(
        "--database-url",
        help="PostgreSQL connection URL (default: from settings)",
    )
    parser.add_argument(
        "--drop-first",
        action="store_true",
        help="Drop existing tables before creating (WARNING: destroys data)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify tables exist, don't run migration",
    )
    args = parser.parse_args()

    # Get database URL
    if args.database_url:
        database_url = args.database_url
    else:
        try:
            from src.config import settings
            database_url = settings.database_url
        except Exception as e:
            print(f"ERROR: Could not load settings: {e}")
            print("Use --database-url to specify connection manually")
            sys.exit(1)

    # Connect to database
    try:
        conn = await get_connection(database_url)
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    try:
        if args.verify_only:
            success = await verify_tables(conn)
            sys.exit(0 if success else 1)

        if args.drop_first:
            confirm = input("This will DELETE ALL DATA. Type 'yes' to confirm: ")
            if confirm.lower() != "yes":
                print("Aborted.")
                sys.exit(0)
            await drop_tables(conn)

        # Read and execute schema
        schema_sql = await read_schema()
        await run_migration(conn, schema_sql)

        # Verify tables were created
        print()
        success = await verify_tables(conn)

        if success:
            print("\n✓ All tables created successfully!")
        else:
            print("\n✗ Some tables are missing. Check errors above.")
            sys.exit(1)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
