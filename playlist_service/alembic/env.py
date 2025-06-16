import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from models import Base

def get_url():
    return os.getenv("PLAYLIST_DB_URL")

config = context.config
config.set_main_option('sqlalchemy.url', get_url())
fileConfig(config.config_file_name)

target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(url=get_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction(): context.run_migrations()
else:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section), prefix='sqlalchemy.', poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction(): context.run_migrations()