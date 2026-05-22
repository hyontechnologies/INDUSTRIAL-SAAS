import os
import shutil
import re

# Map old module path to new module path
# From the perspective of `app.*` or relative to `app/`
MAPPINGS = {
    # Routers
    "routers.admin": "admin.router",
    "routers.grafana": "admin.grafana",
    "routers.alarms": "alarms.router",
    "routers.plants": "plant.router",
    "routers.telemetry": "telemetry.router",
    "routers.tags": "telemetry.tags_router",
    "routers.websocket": "realtime.router",
    # Root files -> infra
    "database": "infra.database",
    "metrics": "infra.metrics",
    # Root files -> identity
    "auth": "identity.auth",
    # Root files -> alarms
    "alarms": "alarms.engine",
    "alarm_consumer": "alarms.consumer",
    # Root files -> realtime
    "broadcaster": "realtime.broadcaster",
    # Root files -> telemetry
    "ingestion": "telemetry.ingestion",
    "stream_consumer": "telemetry.stream_consumer",
    "stream_writer": "telemetry.stream_writer",
    "tag_router": "telemetry.tag_router",
}


def move_file(old_mod, new_mod):
    old_path = os.path.join("app", *old_mod.split(".")) + ".py"
    new_path = os.path.join("app", *new_mod.split(".")) + ".py"

    if os.path.exists(old_path):
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        # If new_path already exists (e.g., from aborted subagent), overwrite it
        if os.path.exists(new_path):
            os.remove(new_path)
        shutil.move(old_path, new_path)
        print(f"Moved {old_path} -> {new_path}")
    else:
        print(f"Skipped {old_path} (not found)")


def update_imports(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = content
    for old_mod, new_mod in MAPPINGS.items():
        # Replace `from app.old_mod import` -> `from app.new_mod import`
        new_content = re.sub(rf"from\s+app\.{old_mod}\s+import", f"from app.{new_mod} import", new_content)
        new_content = re.sub(rf"import\s+app\.{old_mod}(\s|$)", rf"import app.{new_mod}\1", new_content)

        # Replace relative imports: `from .old_mod import` -> `from app.new_mod import`
        # Wait, if we use `from app.new_mod import` everywhere, it's safer than trying to calculate relative paths.
        new_content = re.sub(rf"from\s+\.{old_mod}\s+import", f"from app.{new_mod} import", new_content)

    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated imports in {filepath}")


def main():
    # 1. Move files
    for old_mod, new_mod in MAPPINGS.items():
        move_file(old_mod, new_mod)

    # Remove routers dir if empty
    routers_dir = os.path.join("app", "routers")
    if os.path.exists(routers_dir) and not os.listdir(routers_dir):
        os.rmdir(routers_dir)

    # 2. Update imports in all python files
    for root, _, files in os.walk("app"):
        for file in files:
            if file.endswith(".py"):
                update_imports(os.path.join(root, file))

    # Also update tests
    for root, _, files in os.walk("tests"):
        for file in files:
            if file.endswith(".py"):
                update_imports(os.path.join(root, file))


if __name__ == "__main__":
    main()
