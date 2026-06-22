from __future__ import annotations

import asyncio
import logging

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)


def _upgrade_head() -> None:
    command.upgrade(Config("alembic.ini"), "head")


async def run_startup_migrations() -> None:
    logger.info("Running database migrations to head")
    await asyncio.to_thread(_upgrade_head)
    logger.info("Database migrations finished")
