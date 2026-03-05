from fastapi import Request
from psycopg_pool import AsyncConnectionPool


def build_pool() -> AsyncConnectionPool:
    from emberlog_api.app.core.settings import settings

    database_url = "postgresql://" + \
        settings.postgres_user + ":" + \
        settings.postgres_password + "@" + \
        settings.postgres_host + ":" + \
        str(settings.postgres_port) + "/" + \
        settings.postgres_db
    
    return AsyncConnectionPool(
        database_url,
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        max_idle=60,
    )


def get_pool(request: Request) -> AsyncConnectionPool:
    return request.app.state.pool
