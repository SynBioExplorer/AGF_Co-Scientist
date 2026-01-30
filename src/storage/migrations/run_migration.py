#!/usr/bin/env python3
"""
Migration runner for AI Co-Scientist database.

This script provides a simple interface to run database migrations,
particularly the index creation migration for performance optimization.

Usage:
    python src/storage/migrations/run_migration.py [--all | --migration 001]

Examples:
    # Run all migrations
    python src/storage/migrations/run_migration.py --all

    # Run specific migration
    python src/storage/migrations/run_migration.py --migration 001

    # Check status without running
    python src/storage/migrations/run_migration.py --status
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.storage.postgres import PostgreSQLStorage
import structlog

logger = structlog.get_logger()


async def run_all_migrations(storage: PostgreSQLStorage) -> None:
    """Run all available migrations.

    Args:
        storage: Connected PostgreSQLStorage instance
    """
    logger.info("Running all migrations")

    # Currently only migration 001 exists
    await storage.create_indexes()

    logger.info("All migrations completed successfully")


async def run_specific_migration(storage: PostgreSQLStorage, migration_num: str) -> None:
    """Run a specific migration.

    Args:
        storage: Connected PostgreSQLStorage instance
        migration_num: Migration number (e.g., "001")
    """
    logger.info(f"Running migration {migration_num}")

    if migration_num == "001":
        await storage.create_indexes()
    else:
        logger.error(f"Unknown migration: {migration_num}")
        raise ValueError(f"Migration {migration_num} not found")

    logger.info(f"Migration {migration_num} completed successfully")


async def check_migration_status(storage: PostgreSQLStorage) -> None:
    """Check which migrations have been applied.

    Args:
        storage: Connected PostgreSQLStorage instance
    """
    logger.info("Checking migration status")

    async with storage._acquire_connection() as conn:
        # Check for key indexes from migration 001
        result = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname IN (
                  'idx_hypotheses_goal_status',
                  'idx_hypotheses_goal_elo',
                  'idx_agent_tasks_queue',
                  'idx_reviews_hypothesis_type'
              )
            """
        )

        if result == 4:
            logger.info("Migration 001: ✅ APPLIED (all key indexes exist)")
        elif result > 0:
            logger.warning(f"Migration 001: ⚠️  PARTIALLY APPLIED ({result}/4 key indexes exist)")
        else:
            logger.info("Migration 001: ❌ NOT APPLIED")

        # Get total index count
        total_indexes = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE schemaname = 'public'
            """
        )
        logger.info(f"Total indexes in database: {total_indexes}")

        # Get index usage statistics
        logger.info("Fetching index usage statistics...")
        stats = await conn.fetch(
            """
            SELECT
                tablename,
                indexname,
                idx_scan AS scans,
                pg_size_pretty(pg_relation_size(indexrelid)) AS size
            FROM pg_stat_user_indexes
            WHERE schemaname = 'public'
              AND indexname LIKE 'idx_%'
            ORDER BY idx_scan DESC
            LIMIT 10
            """
        )

        if stats:
            logger.info("Top 10 most-used indexes:")
            for row in stats:
                logger.info(
                    f"  {row['indexname']:45} | Scans: {row['scans']:8} | Size: {row['size']}"
                )
        else:
            logger.info("No index usage statistics available yet")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run database migrations for AI Co-Scientist"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Run all migrations"
    )
    group.add_argument(
        "--migration",
        type=str,
        metavar="NUM",
        help="Run specific migration (e.g., 001)"
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Check migration status without running"
    )

    args = parser.parse_args()

    # Initialize storage
    logger.info("Initializing PostgreSQL storage")
    storage = PostgreSQLStorage()

    try:
        await storage.connect()
        logger.info("Connected to PostgreSQL")

        # Check database connectivity
        if not await storage.health_check():
            logger.error("Database health check failed")
            sys.exit(1)

        # Run migrations
        if args.all:
            await run_all_migrations(storage)
        elif args.migration:
            await run_specific_migration(storage, args.migration)
        elif args.status:
            await check_migration_status(storage)

        logger.info("Migration runner completed successfully")

    except Exception as e:
        logger.error("Migration failed", error=str(e), exc_info=True)
        sys.exit(1)

    finally:
        await storage.disconnect()
        logger.info("Disconnected from PostgreSQL")


if __name__ == "__main__":
    asyncio.run(main())
