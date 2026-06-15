"""
alembic_setup.py — One-time Alembic initialisation helper.
Run this once to scaffold your migrations directory.

Usage:
    python alembic_setup.py
"""
import subprocess
import sys
import textwrap
from pathlib import Path


def run(cmd: str) -> None:
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"[ERROR] Command failed: {cmd}")
        sys.exit(1)


def main() -> None:
    if Path("alembic").exists():
        print("Alembic directory already exists — skipping init.")
    else:
        run("alembic init alembic")

    env_py = Path("alembic/env.py")
    content = env_py.read_text()

    # Patch env.py to use our models and async engine
    if "from app.database import Base" not in content:
        patch = textwrap.dedent("""
            # ── HR API patch ─────────────────────────────────────────────
            from app.config import settings
            from app.database import Base
            import app.models  # noqa: F401 — registers all ORM classes

            config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL)
            target_metadata = Base.metadata
            # ─────────────────────────────────────────────────────────────
        """)
        # Insert after the last import block
        content = content.replace(
            "target_metadata = None",
            "# target_metadata = None  # replaced by HR API patch above",
        )
        content = "# AUTO-PATCHED by alembic_setup.py\n" + patch + "\n" + content
        env_py.write_text(content)
        print("✅  Patched alembic/env.py")

    print("\n✅  Alembic ready. Next steps:")
    print("  alembic revision --autogenerate -m 'initial schema'")
    print("  alembic upgrade head")


if __name__ == "__main__":
    main()
