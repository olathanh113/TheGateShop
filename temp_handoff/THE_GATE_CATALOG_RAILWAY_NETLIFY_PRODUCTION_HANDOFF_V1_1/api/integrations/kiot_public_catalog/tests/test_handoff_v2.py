from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integrations.kiot_public_catalog.deployment_check import (
    validate_deployment_configuration,
)
from integrations.kiot_public_catalog.errors import ConfigurationError


WEBSITE_KEY = "V2_WEBSITE_TEST_KEY_32_CHARACTERS"
INTERNAL_KEY = "V2_INTERNAL_TEST_KEY_32_CHARACTERS"
MODULE_ROOT = Path(__file__).resolve().parents[1]
HANDOFF_API_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = MODULE_ROOT if (MODULE_ROOT / ".env.example").is_file() else HANDOFF_API_ROOT


class DeploymentConfigurationHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.data_dir = self.root / "data"
        self.log_dir = self.root / "logs"
        self.secret_path = self.root / "kiot_secret.env"
        for directory in (self.data_dir, self.log_dir):
            directory.mkdir()
            directory.chmod(0o700)
        self.secret_path.write_text(
            "KV_RETAILER=synthetic-retailer\n"
            "KV_CLIENT_ID=synthetic-client-id\n"
            "KV_CLIENT_SECRET=synthetic-client-secret\n",
            encoding="utf-8",
        )
        self.secret_path.chmod(0o600)
        self.environment = {
            "KIOT_CATALOG_DATA_DIR": str(self.data_dir),
            "KIOT_CATALOG_LOG_DIR": str(self.log_dir),
            "KIOT_CATALOG_SECRETS_PATH": str(self.secret_path),
            "KIOT_CATALOG_WEBSITE_API_KEY": WEBSITE_KEY,
            "KIOT_CATALOG_INTERNAL_API_KEY": INTERNAL_KEY,
            "KIOT_CATALOG_HOST": "127.0.0.1",
            "KIOT_CATALOG_PORT": "8787",
            "KIOT_CATALOG_MAX_PAGE_SIZE": "100",
            "KIOT_CATALOG_RATE_LIMIT_PER_MINUTE": "120",
            "KIOT_CATALOG_MAX_CACHE_AGE_SECONDS": "10800",
            "KIOT_CATALOG_RETAIN_GENERATIONS": "3",
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_v2_config_01_complete_synthetic_configuration_passes_offline(self):
        with patch.dict(os.environ, self.environment, clear=True):
            result = validate_deployment_configuration()
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["network_call_performed"])
        self.assertEqual(result["api_bind"], "loopback")

    def test_v2_config_02_missing_required_path_fails_closed(self):
        environment = dict(self.environment)
        environment.pop("KIOT_CATALOG_DATA_DIR")
        with patch.dict(os.environ, environment, clear=True), self.assertRaisesRegex(
            ConfigurationError, "MISSING_DEPLOYMENT_ENV_KIOT_CATALOG_DATA_DIR"
        ):
            validate_deployment_configuration()

    def test_v2_config_03_missing_secret_file_fails_closed(self):
        environment = dict(self.environment)
        environment["KIOT_CATALOG_SECRETS_PATH"] = str(self.root / "missing.env")
        with patch.dict(os.environ, environment, clear=True), self.assertRaisesRegex(
            ConfigurationError, "SECRET_STORE_MISSING"
        ):
            validate_deployment_configuration()

    def test_v2_config_04_relative_runtime_path_fails_closed(self):
        environment = dict(self.environment)
        environment["KIOT_CATALOG_LOG_DIR"] = "relative/logs"
        with patch.dict(os.environ, environment, clear=True), self.assertRaisesRegex(
            ConfigurationError, "DEPLOYMENT_PATH_NOT_ABSOLUTE_KIOT_CATALOG_LOG_DIR"
        ):
            validate_deployment_configuration()

    def test_v2_config_05_secret_placeholder_fails_closed(self):
        self.secret_path.write_text(
            "KV_RETAILER=synthetic-retailer\n"
            "KV_CLIENT_ID=synthetic-client-id\n"
            "KV_CLIENT_SECRET=replace_me\n",
            encoding="utf-8",
        )
        self.secret_path.chmod(0o600)
        with patch.dict(os.environ, self.environment, clear=True), self.assertRaisesRegex(
            ConfigurationError, "KIOTVIET_CREDENTIAL_IS_PLACEHOLDER"
        ):
            validate_deployment_configuration()

    def test_v2_config_06_handoff_examples_cover_required_contract(self):
        env_text = (CONFIG_ROOT / ".env.example").read_text(encoding="utf-8")
        for name in (
            "KIOT_CATALOG_DATA_DIR",
            "KIOT_CATALOG_LOG_DIR",
            "KIOT_CATALOG_SECRETS_PATH",
        ):
            self.assertIn(name + "=", env_text)
        secret_lines = (
            CONFIG_ROOT / "kiot_secret.env.example"
        ).read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            secret_lines,
            [
                "KV_RETAILER=replace_me",
                "KV_CLIENT_ID=replace_me",
                "KV_CLIENT_SECRET=replace_me",
            ],
        )


if __name__ == "__main__":
    unittest.main()
