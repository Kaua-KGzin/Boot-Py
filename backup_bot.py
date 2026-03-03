#!/usr/bin/env python3
"""Bot de backup robusto com CLI, retencao, checksum e upload opcional para S3."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import logging
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import schedule

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # pragma: no cover - fallback only when boto3 is missing
    boto3 = None
    BotoCoreError = Exception
    ClientError = Exception

VERSION = "1.1.0"
ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class ConfigError(ValueError):
    """Erro lancado quando o arquivo de configuracao e invalido."""


def _validate_time_format(value: str) -> None:
    """Valida formato de horario esperado em HH:MM."""
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise ConfigError("schedule_time deve seguir o formato HH:MM") from exc


@dataclass
class S3Config:
    """Configuracao opcional de upload para S3."""

    enabled: bool = False
    bucket: str = ""
    prefix: str = "backups"
    region_name: str = ""
    endpoint_url: str = ""
    profile_name: str = ""
    storage_class: str = "STANDARD"
    acl: str = ""

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "S3Config":
        data = data or {}
        if not isinstance(data, dict):
            raise ConfigError("s3 deve ser um objeto JSON")
        return cls(
            enabled=bool(data.get("enabled", False)),
            bucket=str(data.get("bucket", "")).strip(),
            prefix=str(data.get("prefix", "backups")).strip(),
            region_name=str(data.get("region_name", "")).strip(),
            endpoint_url=str(data.get("endpoint_url", "")).strip(),
            profile_name=str(data.get("profile_name", "")).strip(),
            storage_class=str(data.get("storage_class", "STANDARD")).strip() or "STANDARD",
            acl=str(data.get("acl", "")).strip(),
        )

    def validate(self) -> None:
        if self.enabled and not self.bucket:
            raise ConfigError("s3.bucket e obrigatorio quando s3.enabled=true")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "bucket": self.bucket,
            "prefix": self.prefix,
            "region_name": self.region_name,
            "endpoint_url": self.endpoint_url,
            "profile_name": self.profile_name,
            "storage_class": self.storage_class,
            "acl": self.acl,
        }


@dataclass
class BackupConfig:
    """Modelo principal de configuracao do backup."""

    backup_dir: Path = Path("./backups")
    source_dirs: List[Path] = field(default_factory=lambda: [Path("./documents"), Path("./projects")])
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    compression: bool = True
    schedule_time: str = "02:00"
    retention_count: int = 7
    exclude_patterns: List[str] = field(default_factory=list)
    log_file: Path = Path("./backup.log")
    log_level: str = "INFO"
    hash_algorithm: str = "sha256"
    s3: S3Config = field(default_factory=S3Config)

    @staticmethod
    def default_dict() -> Dict[str, Any]:
        return {
            "backup_dir": "./backups",
            "source_dirs": ["./documents", "./projects"],
            "max_retries": 3,
            "retry_delay_seconds": 1.0,
            "compression": True,
            "schedule_time": "02:00",
            "retention_count": 7,
            "exclude_patterns": ["*.tmp", "*.log", "__pycache__/*"],
            "log_file": "./backup.log",
            "log_level": "INFO",
            "hash_algorithm": "sha256",
            "s3": {
                "enabled": False,
                "bucket": "",
                "prefix": "backups",
                "region_name": "",
                "endpoint_url": "",
                "profile_name": "",
                "storage_class": "STANDARD",
                "acl": "",
            },
        }

    @classmethod
    def load(cls, config_path: Path) -> "BackupConfig":
        if not config_path.exists():
            config_path.write_text(
                json.dumps(cls.default_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        try:
            raw_data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"JSON invalido no arquivo de configuracao: {exc}") from exc

        if not isinstance(raw_data, dict):
            raise ConfigError("A raiz do config deve ser um objeto JSON")

        defaults = cls.default_dict()
        merged = dict(defaults)
        merged.update({k: v for k, v in raw_data.items() if k != "s3"})
        s3_merged = dict(defaults["s3"])
        if isinstance(raw_data.get("s3"), dict):
            s3_merged.update(raw_data["s3"])
        merged["s3"] = s3_merged

        source_dirs = merged.get("source_dirs", [])
        if not isinstance(source_dirs, list):
            raise ConfigError("source_dirs deve ser uma lista de caminhos")

        exclude_patterns = merged.get("exclude_patterns", [])
        if not isinstance(exclude_patterns, list):
            raise ConfigError("exclude_patterns deve ser uma lista de padroes")

        cfg = cls(
            backup_dir=Path(str(merged.get("backup_dir", "./backups"))),
            source_dirs=[Path(str(path_value)) for path_value in source_dirs],
            max_retries=int(merged.get("max_retries", 3)),
            retry_delay_seconds=float(merged.get("retry_delay_seconds", 1.0)),
            compression=bool(merged.get("compression", True)),
            schedule_time=str(merged.get("schedule_time", "02:00")),
            retention_count=int(merged.get("retention_count", 7)),
            exclude_patterns=[str(pattern) for pattern in exclude_patterns],
            log_file=Path(str(merged.get("log_file", "./backup.log"))),
            log_level=str(merged.get("log_level", "INFO")).upper(),
            hash_algorithm=str(merged.get("hash_algorithm", "sha256")).lower(),
            s3=S3Config.from_dict(merged.get("s3")),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if not self.source_dirs:
            raise ConfigError("source_dirs nao pode estar vazio")
        if self.max_retries < 1:
            raise ConfigError("max_retries deve ser >= 1")
        if self.retry_delay_seconds < 0:
            raise ConfigError("retry_delay_seconds deve ser >= 0")
        if self.retention_count < 1:
            raise ConfigError("retention_count deve ser >= 1")
        if self.log_level not in ALLOWED_LOG_LEVELS:
            raise ConfigError(f"log_level deve ser um destes valores: {', '.join(sorted(ALLOWED_LOG_LEVELS))}")
        if self.hash_algorithm not in hashlib.algorithms_available:
            raise ConfigError(f"hash_algorithm '{self.hash_algorithm}' nao esta disponivel no hashlib")
        _validate_time_format(self.schedule_time)
        self.s3.validate()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backup_dir": str(self.backup_dir),
            "source_dirs": [str(path_value) for path_value in self.source_dirs],
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "compression": self.compression,
            "schedule_time": self.schedule_time,
            "retention_count": self.retention_count,
            "exclude_patterns": self.exclude_patterns,
            "log_file": str(self.log_file),
            "log_level": self.log_level,
            "hash_algorithm": self.hash_algorithm,
            "s3": self.s3.to_dict(),
        }


def setup_logging(log_file: Path, log_level: str) -> logging.Logger:
    """Configura logs no console e em arquivo rotativo."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("backup_bot")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def _human_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{size_bytes} B"


class BackupBot:
    """Automacao de backup com retries, checksum, compressao e retencao."""

    def __init__(self, config: BackupConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.backup_dir = config.backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._s3_client: Any = None

    def _is_excluded(self, source_root: Path, file_path: Path) -> bool:
        relative_path = file_path.relative_to(source_root).as_posix()
        candidates = (relative_path, file_path.name, file_path.as_posix())
        for pattern in self.config.exclude_patterns:
            if any(fnmatch.fnmatch(candidate, pattern) for candidate in candidates):
                return True
        return False

    def collect_files(self) -> Tuple[List[Tuple[Path, Path]], int]:
        """Retorna lista de (diretorio_origem, arquivo_origem) e total excluido."""
        files_to_backup: List[Tuple[Path, Path]] = []
        excluded_count = 0

        for source_dir in self.config.source_dirs:
            if not source_dir.exists():
                self.logger.warning("Diretorio de origem nao encontrado: %s", source_dir)
                continue
            if not source_dir.is_dir():
                self.logger.warning("Caminho de origem nao e diretorio: %s", source_dir)
                continue

            for file_path in source_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                if self._is_excluded(source_dir, file_path):
                    excluded_count += 1
                    continue
                files_to_backup.append((source_dir, file_path))

        files_to_backup.sort(key=lambda item: item[1].as_posix())
        return files_to_backup, excluded_count

    def calculate_checksum(self, file_path: Path) -> str:
        """Calcula checksum do arquivo usando algoritmo configurado."""
        digest = hashlib.new(self.config.hash_algorithm)
        with file_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def backup_file(self, source_root: Path, source_file: Path, destination_root: Path) -> bool:
        """Faz backup de um arquivo com retry e validacao de integridade."""
        for attempt in range(1, self.config.max_retries + 1):
            try:
                relative_path = source_file.relative_to(source_root)
                destination_file = destination_root / source_root.name / relative_path
                destination_file.parent.mkdir(parents=True, exist_ok=True)

                shutil.copy2(source_file, destination_file)

                source_checksum = self.calculate_checksum(source_file)
                destination_checksum = self.calculate_checksum(destination_file)
                if source_checksum != destination_checksum:
                    raise IOError("Checksum divergente apos copia")

                self.logger.debug("Backup concluido: %s -> %s", source_file, destination_file)
                return True
            except PermissionError:
                self.logger.warning(
                    "Erro de permissao ao copiar %s (tentativa %s/%s)",
                    source_file,
                    attempt,
                    self.config.max_retries,
                )
            except Exception as exc:
                self.logger.error(
                    "Falha ao copiar %s (tentativa %s/%s): %s",
                    source_file,
                    attempt,
                    self.config.max_retries,
                    exc,
                )

            if attempt < self.config.max_retries:
                time.sleep(self.config.retry_delay_seconds)

        return False

    def compress_backup(self, backup_folder: Path) -> Path:
        """Comprime a pasta de backup e remove diretorio original."""
        archive_path = backup_folder.with_suffix(".zip")
        if archive_path.exists():
            archive_path.unlink()

        shutil.make_archive(str(backup_folder), "zip", root_dir=backup_folder)
        shutil.rmtree(backup_folder)
        self.logger.info("Backup comprimido: %s", archive_path.name)
        return archive_path

    def _get_s3_client(self) -> Any:
        if not self.config.s3.enabled:
            return None
        if boto3 is None:
            raise RuntimeError("boto3 nao esta instalado, mas s3.enabled=true")
        if self._s3_client is not None:
            return self._s3_client

        session_kwargs: Dict[str, Any] = {}
        if self.config.s3.profile_name:
            session_kwargs["profile_name"] = self.config.s3.profile_name
        session = boto3.session.Session(**session_kwargs)

        client_kwargs: Dict[str, Any] = {}
        if self.config.s3.region_name:
            client_kwargs["region_name"] = self.config.s3.region_name
        if self.config.s3.endpoint_url:
            client_kwargs["endpoint_url"] = self.config.s3.endpoint_url

        self._s3_client = session.client("s3", **client_kwargs)
        return self._s3_client

    def _upload_file_to_s3(self, file_path: Path, key: str) -> None:
        client = self._get_s3_client()
        if client is None:
            return
        extra_args: Dict[str, Any] = {"StorageClass": self.config.s3.storage_class}
        if self.config.s3.acl:
            extra_args["ACL"] = self.config.s3.acl
        client.upload_file(str(file_path), self.config.s3.bucket, key, ExtraArgs=extra_args)

    def upload_artifact(self, artifact_path: Path, backup_name: str) -> Dict[str, Any]:
        """Envia artefato de backup para S3 quando habilitado."""
        result = {"enabled": self.config.s3.enabled, "uploaded": 0, "failed": 0, "errors": []}
        if not self.config.s3.enabled:
            return result

        prefix = self.config.s3.prefix.strip("/")
        upload_targets: List[Tuple[Path, str]] = []
        if artifact_path.is_file():
            key = "/".join(part for part in [prefix, artifact_path.name] if part)
            upload_targets.append((artifact_path, key))
        else:
            for file_path in artifact_path.rglob("*"):
                if file_path.is_file():
                    relative_key = file_path.relative_to(artifact_path).as_posix()
                    key = "/".join(part for part in [prefix, backup_name, relative_key] if part)
                    upload_targets.append((file_path, key))

        for file_path, key in upload_targets:
            try:
                self._upload_file_to_s3(file_path, key)
                result["uploaded"] += 1
            except (BotoCoreError, ClientError, RuntimeError, OSError) as exc:
                result["failed"] += 1
                result["errors"].append(f"{file_path.name}: {exc}")
                self.logger.error("Falha no upload S3 para %s: %s", file_path, exc)

        return result

    def _cleanup_path(self, path_obj: Path) -> None:
        if path_obj.is_dir():
            shutil.rmtree(path_obj, ignore_errors=True)
        elif path_obj.exists():
            path_obj.unlink()

    def apply_retention(self) -> None:
        """Mantem apenas backups e relatorios mais recentes."""
        backups = sorted(
            self.backup_dir.glob("backup_*"),
            key=lambda path_value: path_value.stat().st_mtime,
            reverse=True,
        )
        for old_backup in backups[self.config.retention_count :]:
            self._cleanup_path(old_backup)
            self.logger.info("Retencao removeu: %s", old_backup.name)

        reports = sorted(
            self.backup_dir.glob("report_*.json"),
            key=lambda path_value: path_value.stat().st_mtime,
            reverse=True,
        )
        for old_report in reports[self.config.retention_count :]:
            self._cleanup_path(old_report)
            self.logger.info("Retencao removeu: %s", old_report.name)

    def generate_report(self, stats: Dict[str, Any], report_suffix: str) -> Path:
        report_path = self.backup_dir / f"report_{report_suffix}.json"
        report_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
        return report_path

    def log_summary(self, stats: Dict[str, Any]) -> None:
        self.logger.info(
            "Resumo | total=%s sucesso=%s falhas=%s ignorados=%s excluidos=%s tamanho=%s duracao=%ss",
            stats["total_files"],
            stats["success"],
            stats["failed"],
            stats["skipped"],
            stats["excluded"],
            _human_size(stats["total_size_bytes"]),
            stats["duration_seconds"],
        )

    def run_backup(self, dry_run: bool = False, compression_override: Optional[bool] = None) -> Dict[str, Any]:
        """Executa o processo de backup e retorna estatisticas."""
        started_at = datetime.now()
        backup_suffix = started_at.strftime("%Y%m%d_%H%M%S_%f")
        backup_name = f"backup_{backup_suffix}"
        backup_folder = self.backup_dir / backup_name

        self.logger.info("Iniciando backup | dry_run=%s", dry_run)
        file_pairs, excluded_count = self.collect_files()

        stats: Dict[str, Any] = {
            "version": VERSION,
            "dry_run": dry_run,
            "total_files": len(file_pairs),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "excluded": excluded_count,
            "total_size_bytes": 0,
            "start_time": started_at.isoformat(),
            "artifact_path": "",
            "upload": {"enabled": self.config.s3.enabled, "uploaded": 0, "failed": 0, "errors": []},
        }

        if dry_run:
            stats["skipped"] = len(file_pairs)
            self.logger.info("Dry-run concluido. %s arquivos seriam copiados.", len(file_pairs))
        else:
            backup_folder.mkdir(parents=True, exist_ok=False)
            for source_root, source_file in file_pairs:
                if self.backup_file(source_root, source_file, backup_folder):
                    stats["success"] += 1
                    try:
                        stats["total_size_bytes"] += source_file.stat().st_size
                    except OSError:
                        self.logger.warning("Nao foi possivel ler tamanho do arquivo: %s", source_file)
                else:
                    stats["failed"] += 1

            compression_enabled = self.config.compression if compression_override is None else compression_override
            artifact_path = backup_folder
            if compression_enabled:
                try:
                    artifact_path = self.compress_backup(backup_folder)
                except Exception as exc:
                    stats["failed"] += 1
                    self.logger.error("Falha na compressao, mantendo pasta sem compactar: %s", exc)

            stats["artifact_path"] = str(artifact_path.resolve())
            stats["upload"] = self.upload_artifact(artifact_path, backup_name)

        ended_at = datetime.now()
        stats["end_time"] = ended_at.isoformat()
        stats["duration_seconds"] = round((ended_at - started_at).total_seconds(), 3)
        report_path = self.generate_report(stats, backup_suffix)
        stats["report_path"] = str(report_path.resolve())
        self.apply_retention()
        self.log_summary(stats)
        return stats

    def schedule_backup(self, run_now: bool = False) -> None:
        """Agenda backups diarios e mantem processo em execucao."""
        if run_now:
            self.run_backup()
        schedule.every().day.at(self.config.schedule_time).do(self.run_backup)
        self.logger.info("Backup diario agendado para %s", self.config.schedule_time)

        try:
            while True:
                schedule.run_pending()
                time.sleep(30)
        except KeyboardInterrupt:
            self.logger.info("Agendador interrompido pelo usuario.")


def init_config(config_path: Path, force: bool = False) -> int:
    if config_path.exists() and not force:
        print(f"Config ja existe em {config_path}. Use --force para sobrescrever.")
        return 1

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(BackupConfig.default_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Config criada em {config_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backup Bot - automacao de backup confiavel")
    parser.add_argument("--config", default="config.json", help="Caminho para o arquivo config JSON")
    parser.add_argument(
        "--log-level",
        choices=sorted(ALLOWED_LOG_LEVELS),
        help="Sobrescreve nivel de log definido no config",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init-config", help="Cria arquivo de config padrao")
    init_parser.add_argument("--force", action="store_true", help="Sobrescreve config existente")

    subparsers.add_parser("validate-config", help="Valida config e imprime saida normalizada")
    subparsers.add_parser("show-config", help="Imprime config normalizado e sai")

    run_parser = subparsers.add_parser("run", help="Executa backup agora")
    run_parser.add_argument("--dry-run", action="store_true", help="Simula backup sem gravar arquivos")
    run_parser.add_argument("--no-compress", action="store_true", help="Desativa compressao neste backup")

    schedule_parser = subparsers.add_parser("schedule", help="Executa em modo agendador")
    schedule_parser.add_argument("--run-now", action="store_true", help="Executa um backup antes de agendar")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config_path = Path(args.config)

    if args.command == "init-config":
        return init_config(config_path, force=args.force)

    try:
        config = BackupConfig.load(config_path)
    except (ConfigError, OSError) as exc:
        print(f"Erro de configuracao: {exc}", file=sys.stderr)
        return 2

    if args.command == "validate-config":
        print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))
        print("Config valido.")
        return 0

    if args.command == "show-config":
        print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))
        return 0

    logger = setup_logging(config.log_file, args.log_level or config.log_level)
    bot = BackupBot(config, logger)

    if args.command in (None, "run"):
        dry_run = bool(getattr(args, "dry_run", False))
        no_compress = bool(getattr(args, "no_compress", False))
        stats = bot.run_backup(dry_run=dry_run, compression_override=False if no_compress else None)
        return 1 if stats["failed"] else 0

    if args.command == "schedule":
        bot.schedule_backup(run_now=args.run_now)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
