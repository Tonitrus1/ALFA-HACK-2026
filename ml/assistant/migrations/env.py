from alembic import context
from sqlalchemy import create_engine

from alfa_assistant.config import Settings
from alfa_assistant.storage import Base

settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
engine = create_engine(settings.database_url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
