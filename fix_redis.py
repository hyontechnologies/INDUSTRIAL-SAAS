import os


def fix_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    content = content.replace(
        "from app.telemetry.stream_writer import redis_client", "from app.infra.redis import get_redis"
    )
    content = content.replace(
        "from .redis import init_redis_pool, close_redis_pool, redis_client",
        "from .redis import init_redis_pool, close_redis_pool, get_redis",
    )
    content = content.replace('"redis_client",', '"get_redis",')
    content = content.replace(
        "from app.telemetry.stream_writer import init_redis_pool, close_redis_pool, redis_client",
        "from app.infra.redis import init_redis_pool, close_redis_pool, get_redis",
    )

    # Replace usages
    content = content.replace("redis_client.", "get_redis().")
    content = content.replace("redis_client:", "get_redis():")
    content = content.replace("if redis_client", "if get_redis()")
    content = content.replace("if not redis_client", "if not get_redis()")

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Fixed {filepath}")


for root, dirs, files in os.walk(
    "C:/Users/srikh/.gemini/antigravity/worktrees/Industrial-SAAS/industrial-telemetry-platform-init/backend/app"
):
    for file in files:
        if file.endswith(".py") and file != "redis.py":
            fix_file(os.path.join(root, file))
