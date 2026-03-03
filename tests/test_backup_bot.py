import json
import logging
import tempfile
import time
import unittest
from pathlib import Path

from backup_bot import BackupBot, BackupConfig, ConfigError, setup_logging


class BackupBotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.docs_dir = self.root / "documents"
        self.projects_dir = self.root / "projects"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

        (self.docs_dir / "file1.txt").write_text("hello", encoding="utf-8")
        (self.docs_dir / "ignore.tmp").write_text("temporary", encoding="utf-8")
        (self.projects_dir / "app.py").write_text("print('ok')", encoding="utf-8")

        self.config_path = self.root / "config.json"
        config_data = BackupConfig.default_dict()
        config_data.update(
            {
                "backup_dir": str(self.root / "backups"),
                "source_dirs": [str(self.docs_dir), str(self.projects_dir)],
                "log_file": str(self.root / "backup.log"),
                "exclude_patterns": ["*.tmp"],
                "compression": True,
                "retention_count": 2,
                "s3": {"enabled": False},
            }
        )
        self.config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

        self.config = BackupConfig.load(self.config_path)
        self.logger = setup_logging(self.config.log_file, "DEBUG")
        self.bot = BackupBot(self.config, self.logger)

    def tearDown(self) -> None:
        logger = logging.getLogger("backup_bot")
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
        self.temp_dir.cleanup()

    def test_config_validation_invalid_schedule(self) -> None:
        bad_config = BackupConfig.default_dict()
        bad_config["source_dirs"] = [str(self.docs_dir)]
        bad_config["schedule_time"] = "99:99"
        bad_path = self.root / "bad_config.json"
        bad_path.write_text(json.dumps(bad_config), encoding="utf-8")

        with self.assertRaises(ConfigError):
            BackupConfig.load(bad_path)

    def test_run_backup_success_with_compression(self) -> None:
        stats = self.bot.run_backup()

        self.assertEqual(stats["total_files"], 2)
        self.assertEqual(stats["excluded"], 1)
        self.assertEqual(stats["success"], 2)
        self.assertEqual(stats["failed"], 0)
        self.assertTrue(stats["artifact_path"].endswith(".zip"))

        artifact_path = Path(stats["artifact_path"])
        report_path = Path(stats["report_path"])
        self.assertTrue(artifact_path.exists())
        self.assertTrue(report_path.exists())

    def test_dry_run_creates_report_only(self) -> None:
        stats = self.bot.run_backup(dry_run=True)

        self.assertEqual(stats["total_files"], 2)
        self.assertEqual(stats["skipped"], 2)
        self.assertEqual(stats["success"], 0)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["artifact_path"], "")

        artifacts = list((self.root / "backups").glob("backup_*"))
        self.assertEqual(len(artifacts), 0)
        self.assertTrue(Path(stats["report_path"]).exists())

    def test_retention_keeps_latest_backup_and_report(self) -> None:
        self.bot.config.compression = False
        self.bot.config.retention_count = 1

        first = self.bot.run_backup()
        time.sleep(1.1)
        second = self.bot.run_backup()

        backups = sorted((self.root / "backups").glob("backup_*"))
        reports = sorted((self.root / "backups").glob("report_*.json"))

        self.assertEqual(len(backups), 1)
        self.assertEqual(len(reports), 1)
        self.assertTrue(Path(second["artifact_path"]).exists())
        self.assertFalse(Path(first["artifact_path"]).exists())


if __name__ == "__main__":
    unittest.main()
