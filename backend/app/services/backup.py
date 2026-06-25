"""Backup and restore service for the Password Manager.

Creates .tgz archives containing:
1. PostgreSQL database dump (all tables)
2. Encryption key file
3. RSA key files (private + public)
4. Metadata JSON (timestamp, version, etc.)

Restores from a backup by:
1. Extracting the .tgz
2. Restoring the database from SQL dump
3. Restoring the encryption key
4. Restoring RSA keys
5. Verifying integrity
"""

import asyncio
import json
import os
import shutil
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from app.config import settings
from app.database import engine

# Backup storage directory
_BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/tmp/password-manager-backups"))


class BackupService:
    """Service for creating and restoring backups."""

    BACKUP_VERSION = "1.0"
    BACKUP_FILENAME_PREFIX = "password-manager-backup"

    @classmethod
    def _ensure_backup_dir(cls) -> Path:
        """Ensure backup directory exists with restricted permissions."""
        _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(_BACKUP_DIR, 0o700)
        return _BACKUP_DIR

    @classmethod
    async def get_backup_status(cls) -> dict:
        """Get backup status including counts and last backup info."""
        from app.database import async_session
        from app.models.user import User
        from app.models.group import Group
        from app.models.secret import Secret

        async with async_session() as session:
            user_count = (await session.execute(
                session.query(User).count()
            )).scalar() if hasattr(session, 'query') else 0
            # Fallback: use select
            from sqlalchemy import func
            result = await session.execute(func.count(User.id))
            user_count = result.scalar()

            result = await session.execute(func.count(Group.id))
            group_count = result.scalar()

            result = await session.execute(func.count(Secret.id))
            secret_count = result.scalar()

        backups = cls.list_backups()
        last_backup = backups[0] if backups else None

        return {
            "user_count": user_count,
            "group_count": group_count,
            "secret_count": secret_count,
            "backup_count": len(backups),
            "last_backup_at": last_backup["created_at"] if last_backup else None,
            "status": "operational" if len(backups) > 0 else "no_backups",
            "message": f"{len(backups)} backup(s) available" if backups else "No backups available. Execute a backup first.",
        }

    @classmethod
    def list_backups(cls) -> list[dict]:
        """List all available backups."""
        backup_dir = cls._ensure_backup_dir()
        backups = []

        for tgz_file in sorted(backup_dir.glob(f"{cls.BACKUP_FILENAME_PREFIX}-*.tgz")):
            stat = tgz_file.stat()
            backups.append({
                "backup_id": tgz_file.stem.replace(f"{cls.BACKUP_FILENAME_PREFIX}-", ""),
                "filename": tgz_file.name,
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "size_bytes": stat.st_size,
                "status": "available",
                "message": "Backup available",
            })

        return backups

    @classmethod
    async def execute_backup(cls) -> dict:
        """Execute a full backup of the database and encryption keys."""
        backup_dir = cls._ensure_backup_dir()
        backup_id = f"{cls.BACKUP_FILENAME_PREFIX}-{uuid.uuid4().hex[:8]}"
        backup_path = backup_dir / f"{backup_id}.tgz"

        # Create a temporary directory for backup contents
        temp_dir = backup_dir / f"{backup_id}-temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Export database to SQL
            await cls._export_database(temp_dir / "database.sql")

            # 2. Export encryption key
            encryption_key_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "app", ".encryption_key"
            )
            encryption_key_path = os.path.normpath(encryption_key_path)
            if os.path.exists(encryption_key_path):
                shutil.copy2(
                    encryption_key_path,
                    temp_dir / "encryption_key"
                )

            # 3. Export RSA keys
            rsa_keys_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "app", "utils", "keys"
            )
            rsa_keys_dir = os.path.normpath(rsa_keys_dir)
            if os.path.exists(rsa_keys_dir):
                rsa_dest = temp_dir / "rsa_keys"
                rsa_dest.mkdir(exist_ok=True)
                for key_file in ["jwt_private.pem", "jwt_public.pem"]:
                    src = os.path.join(rsa_keys_dir, key_file)
                    if os.path.exists(src):
                        shutil.copy2(src, rsa_dest / key_file)

            # 4. Create metadata JSON
            metadata = {
                "version": cls.BACKUP_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "backup_id": backup_id,
                "encryption_key_present": os.path.exists(temp_dir / "encryption_key"),
                "rsa_keys_present": os.path.exists(temp_dir / "rsa_keys"),
            }
            with open(temp_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            # 5. Create .tgz archive
            with tarfile.open(backup_path, "w:gz") as tar:
                for item in temp_dir.iterdir():
                    tar.add(str(item), arcname=item.name)

            # Set restrictive permissions on the backup file
            os.chmod(backup_path, 0o600)

            # Clean up temp directory
            shutil.rmtree(temp_dir)

            return {
                "backup_id": backup_id,
                "status": "completed",
                "message": f"Backup {backup_id} created successfully",
                "path": str(backup_path),
            }

        except Exception as e:
            # Clean up on failure
            shutil.rmtree(temp_dir, ignore_errors=True)
            if backup_path.exists():
                backup_path.unlink()
            raise HTTPException(
                status_code=500,
                detail=f"Backup failed: {str(e)}"
            )

    @classmethod
    async def _export_database(cls, output_path: Path) -> None:
        """Export the PostgreSQL database to a SQL file."""
        # Get database URL from settings
        db_url = settings.DATABASE_URL

        # Use pg_dump if available
        pg_dump_path = shutil.which("pg_dump")
        if pg_dump_path:
            # Parse database URL to get connection parameters
            # Format: postgresql+asyncpg://user:password@host:port/dbname
            import re
            match = re.match(
                r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)(?:\?.*)?",
                db_url
            )
            if match:
                user, password, host, port, dbname = match.groups()
                env = os.environ.copy()
                env["PGPASSWORD"] = password

                proc = await asyncio.create_subprocess_exec(
                    pg_dump_path,
                    "-U", user,
                    "-h", host,
                    "-p", port,
                    "-d", dbname,
                    "-f", str(output_path),
                    "--no-owner",
                    "--no-privileges",
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()

                if proc.returncode != 0:
                    raise RuntimeError(f"pg_dump failed: {stderr.decode()}")
                return

        # Fallback: export using SQLAlchemy
        await cls._export_database_sqlalchemy(output_path)

    @classmethod
    async def _export_database_sqlalchemy(cls, output_path: Path) -> None:
        """Export database using SQLAlchemy (fallback method).

        Only exports tables that have SQLAlchemy models to avoid
        'column not found' errors on system/legacy tables.
        """
        from app.database import Base, async_session
        from sqlalchemy import text

        # Only export tables that have SQLAlchemy models defined
        tables_to_export = list(Base.metadata.tables.keys())

        async with async_session() as session:
            # Verify tables actually exist in the database
            existing_tables = await session.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            ))
            existing_table_names = {row[0] for row in existing_tables.all()}

            tables_to_export = [
                t for t in tables_to_export if t in existing_table_names
            ]

            with open(output_path, "w") as f:
                f.write("-- Password Manager Database Backup\n")
                f.write(f"-- Generated at: {datetime.now(timezone.utc).isoformat()}\n\n")

                for table in tables_to_export:
                    try:
                        # Export table data
                        result = await session.execute(text(f"SELECT * FROM {table}"))
                        rows = result.all()

                        if rows:
                            # Get column names
                            col_names = list(rows[0].keys())
                            f.write(f"-- Table: {table}\n")

                            for row in rows:
                                values = []
                                for col in col_names:
                                    val = row[col]
                                    if val is None:
                                        values.append("NULL")
                                    elif isinstance(val, str):
                                        # Escape single quotes
                                        escaped = val.replace("'", "''")
                                        values.append(f"'{escaped}'")
                                    elif isinstance(val, datetime):
                                        values.append(f"'{val.isoformat()}'")
                                    else:
                                        values.append(str(val))

                                f.write(f"INSERT INTO {table} ({', '.join(col_names)}) VALUES ({', '.join(values)});\n")
                            f.write("\n")
                    except Exception as e:
                        f.write(f"-- ERROR exporting table '{table}': {e}\n\n")

    @classmethod
    async def restore_backup(cls, backup_id: str) -> dict:
        """Restore from a backup."""
        backup_dir = cls._ensure_backup_dir()
        backup_file = backup_dir / f"{backup_id}.tgz"

        if not backup_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Backup {backup_id} not found"
            )

        # Create a temporary directory for extraction
        temp_dir = backup_dir / f"{backup_id}-restore-temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Extract the backup
            with tarfile.open(backup_file, "r:gz") as tar:
                tar.extractall(path=str(temp_dir))

            # 2. Verify metadata
            metadata_path = temp_dir / "metadata.json"
            if not metadata_path.exists():
                raise HTTPException(
                    status_code=400,
                    detail="Invalid backup: missing metadata.json"
                )

            with open(metadata_path) as f:
                metadata = json.load(f)

            # 3. Restore database
            database_sql = temp_dir / "database.sql"
            if database_sql.exists():
                await cls._import_database(database_sql)

            # 4. Restore encryption key
            encryption_key_src = temp_dir / "encryption_key"
            if encryption_key_src.exists():
                encryption_key_dest = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "..", "app", ".encryption_key"
                )
                encryption_key_dest = os.path.normpath(encryption_key_dest)
                shutil.copy2(encryption_key_src, encryption_key_dest)
                os.chmod(encryption_key_dest, 0o600)

            # 5. Restore RSA keys
            rsa_keys_src = temp_dir / "rsa_keys"
            if rsa_keys_src.exists():
                rsa_keys_dest = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "..", "app", "utils", "keys"
                )
                rsa_keys_dest = os.path.normpath(rsa_keys_dest)
                for key_file in rsa_keys_src.iterdir():
                    dest = os.path.join(rsa_keys_dest, key_file.name)
                    shutil.copy2(key_file, dest)
                    os.chmod(dest, 0o600)

            # Clean up temp directory
            shutil.rmtree(temp_dir)

            return {
                "backup_id": backup_id,
                "status": "completed",
                "message": f"Backup {backup_id} restored successfully",
            }

        except HTTPException:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=500,
                detail=f"Restore failed: {str(e)}"
            )

    @classmethod
    async def _import_database(cls, sql_path: Path) -> None:
        """Import database from a SQL file."""
        # Use psql if available
        psql_path = shutil.which("psql")
        if psql_path:
            import re
            db_url = settings.DATABASE_URL
            match = re.match(
                r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)(?:\?.*)?",
                db_url
            )
            if match:
                user, password, host, port, dbname = match.groups()
                env = os.environ.copy()
                env["PGPASSWORD"] = password

                proc = await asyncio.create_subprocess_exec(
                    psql_path,
                    "-U", user,
                    "-h", host,
                    "-p", port,
                    "-d", dbname,
                    "-f", str(sql_path),
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()

                if proc.returncode != 0:
                    raise RuntimeError(f"psql failed: {stderr.decode()}")
                return

        # Fallback: execute SQL using SQLAlchemy
        with open(sql_path) as f:
            sql_content = f.read()

        from app.database import async_session
        from sqlalchemy import text

        async with async_session() as session:
            # Execute SQL statements
            statements = [s.strip() for s in sql_content.split(";") if s.strip() and not s.strip().startswith("--")]
            for statement in statements:
                try:
                    await session.execute(text(statement))
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    raise RuntimeError(f"SQL execution failed: {str(e)}\nSQL: {statement[:100]}")
