from __future__ import with_statement
from alembic import context
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig

# استيراد تطبيقك وقاعدة البيانات
import os
import sys
# تأكد من أن Alembic يمكنه العثور على ملفات مشروعك
sys.path.append(os.getcwd())

from app import app, db
from models import User, Transaction

# هذا هو كائن إعدادات Alembic
config = context.config

# إعدادات التسجيل
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# هنا يتم ربط MetaData بنموذج قاعدة البيانات
target_metadata = db.metadata

def run_migrations_offline():
    """تشغيل الترحيل في وضع عدم الاتصال"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """تشغيل الترحيل في وضع الاتصال"""
    # هنا يتم إنشاء سياق التطبيق لتوفير الوصول إلى 'app' و 'db'
    with app.app_context():
        connectable = db.engine

        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata
            )

            with context.begin_transaction():
                context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()