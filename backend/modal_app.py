"""Modal deployment for the existing FastAPI application.

The function scales to zero when idle. Resource sizes are deliberately capped to
one container; model work remains isolated inside the API's existing worker code.
"""

import modal


APP_NAME = "review-sentiment-api"
SECRET_NAME = "review-sentiment-production"

app = modal.App(APP_NAME)
image = modal.Image.from_dockerfile(
    "Dockerfile",
    context_dir=".",
    build_args={"TARGETARCH": "amd64"},
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    cpu=2,
    memory=8192,
    min_containers=0,
    max_containers=1,
    scaledown_window=60,
    timeout=240,
    region="ap",
    routing_region="ap-south",
)
@modal.asgi_app()
def api():
    from backend.app.main import app as fastapi_app

    return fastapi_app


@app.function(
    image=image,
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    cpu=1,
    memory=1024,
    timeout=300,
)
def migrate_database():
    """Apply the checked-in Alembic migrations to the configured Neon database."""
    import subprocess

    print("alembic_upgrade_started", flush=True)
    subprocess.run(
        ["python", "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
        check=True,
    )
    print("alembic_upgrade_completed", flush=True)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    cpu=1,
    memory=1024,
    timeout=60,
)
def diagnose_database():
    """Report only schema revision and registry row ids for deployment diagnosis."""
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    from backend.app.config import database_url
    from sqlalchemy import create_engine

    engine = create_engine(database_url(), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            rows = connection.execute(text("SELECT model_id FROM model_registry ORDER BY model_id")).scalars().all()
        print(f"database_diagnostic revision={revision!r} models={rows!r}", flush=True)
    except SQLAlchemyError as exc:
        print(f"database_diagnostic error_type={type(exc).__name__}", flush=True)
    finally:
        engine.dispose()


@app.local_entrypoint()
def diagnose():
    diagnose_database.remote()


@app.local_entrypoint()
def migrate():
    """Invoke the one-time remote migration helper."""
    migrate_database.remote()
