"""Scheduler for automated data syncing."""

import logging
import platform
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Manages scheduled sync operations."""

    def __init__(self, sync_interval: int = 3600):
        """Initialize scheduler.

        Args:
            sync_interval: Sync interval in seconds
        """
        self.sync_interval = sync_interval
        self.platform = platform.system()

    def install_schedule(self, script_path: str) -> bool:
        """Install scheduled sync based on platform.

        Args:
            script_path: Path to the sync script/command

        Returns:
            True if successful, False otherwise
        """
        if self.platform == "Darwin":
            return self._install_launchd(script_path)
        elif self.platform == "Linux":
            return self._install_systemd(script_path)
        else:
            logger.error(f"Unsupported platform: {self.platform}")
            return False

    def uninstall_schedule(self) -> bool:
        """Uninstall scheduled sync.

        Returns:
            True if successful, False otherwise
        """
        if self.platform == "Darwin":
            return self._uninstall_launchd()
        elif self.platform == "Linux":
            return self._uninstall_systemd()
        else:
            logger.error(f"Unsupported platform: {self.platform}")
            return False

    def _install_launchd(self, script_path: str) -> bool:
        """Install launchd service on macOS.

        Args:
            script_path: Path to the sync script

        Returns:
            True if successful
        """
        try:
            launchd_dir = Path.home() / "Library" / "LaunchAgents"
            launchd_dir.mkdir(parents=True, exist_ok=True)

            plist_file = launchd_dir / "com.withings.exporter.plist"

            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.withings.exporter</string>
    <key>ProgramArguments</key>
    <array>
        <string>{script_path}</string>
        <string>sync</string>
    </array>
    <key>StartInterval</key>
    <integer>{self.sync_interval}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{Path.home()}/.withings/logs/sync.log</string>
    <key>StandardErrorPath</key>
    <string>{Path.home()}/.withings/logs/sync_error.log</string>
</dict>
</plist>
"""

            with open(plist_file, 'w') as f:
                f.write(plist_content)

            # Load the launch agent
            subprocess.run(['launchctl', 'load', str(plist_file)], check=True)

            logger.info(f"Installed launchd service at {plist_file}")
            logger.info(f"Sync will run every {self.sync_interval} seconds")
            return True

        except Exception as e:
            logger.error(f"Error installing launchd service: {e}")
            return False

    def _uninstall_launchd(self) -> bool:
        """Uninstall launchd service on macOS.

        Returns:
            True if successful
        """
        try:
            plist_file = Path.home() / "Library" / "LaunchAgents" / "com.withings.exporter.plist"

            if plist_file.exists():
                # Unload the launch agent
                subprocess.run(['launchctl', 'unload', str(plist_file)], check=False)

                # Remove the plist file
                plist_file.unlink()

                logger.info("Uninstalled launchd service")
                return True
            else:
                logger.info("No launchd service found to uninstall")
                return True

        except Exception as e:
            logger.error(f"Error uninstalling launchd service: {e}")
            return False

    def _install_systemd(self, script_path: str) -> bool:
        """Install systemd service on Linux.

        Args:
            script_path: Path to the sync script

        Returns:
            True if successful
        """
        try:
            systemd_dir = Path.home() / ".config" / "systemd" / "user"
            systemd_dir.mkdir(parents=True, exist_ok=True)

            service_file = systemd_dir / "withings-exporter.service"
            timer_file = systemd_dir / "withings-exporter.timer"

            # Create service file
            service_content = f"""[Unit]
Description=Withings Health Data Exporter
After=network.target

[Service]
Type=oneshot
ExecStart={script_path} sync
StandardOutput=append:{Path.home()}/.withings/logs/sync.log
StandardError=append:{Path.home()}/.withings/logs/sync_error.log

[Install]
WantedBy=default.target
"""

            with open(service_file, 'w') as f:
                f.write(service_content)

            # Create timer file
            timer_content = f"""[Unit]
Description=Withings Health Data Exporter Timer
Requires=withings-exporter.service

[Timer]
OnBootSec={self.sync_interval}s
OnUnitActiveSec={self.sync_interval}s
Unit=withings-exporter.service

[Install]
WantedBy=timers.target
"""

            with open(timer_file, 'w') as f:
                f.write(timer_content)

            # Reload systemd and enable timer
            subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
            subprocess.run(['systemctl', '--user', 'enable', 'withings-exporter.timer'], check=True)
            subprocess.run(['systemctl', '--user', 'start', 'withings-exporter.timer'], check=True)

            logger.info(f"Installed systemd service at {service_file}")
            logger.info(f"Installed systemd timer at {timer_file}")
            logger.info(f"Sync will run every {self.sync_interval} seconds")
            return True

        except Exception as e:
            logger.error(f"Error installing systemd service: {e}")
            return False

    def _uninstall_systemd(self) -> bool:
        """Uninstall systemd service on Linux.

        Returns:
            True if successful
        """
        try:
            systemd_dir = Path.home() / ".config" / "systemd" / "user"
            service_file = systemd_dir / "withings-exporter.service"
            timer_file = systemd_dir / "withings-exporter.timer"

            # Stop and disable timer
            subprocess.run(['systemctl', '--user', 'stop', 'withings-exporter.timer'], check=False)
            subprocess.run(['systemctl', '--user', 'disable', 'withings-exporter.timer'], check=False)

            # Remove files
            if timer_file.exists():
                timer_file.unlink()
            if service_file.exists():
                service_file.unlink()

            # Reload systemd
            subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)

            logger.info("Uninstalled systemd service")
            return True

        except Exception as e:
            logger.error(f"Error uninstalling systemd service: {e}")
            return False

    def get_status(self) -> Optional[str]:
        """Get scheduler status.

        Returns:
            Status string or None
        """
        if self.platform == "Darwin":
            return self._get_launchd_status()
        elif self.platform == "Linux":
            return self._get_systemd_status()
        else:
            return "Unsupported platform"

    def _get_launchd_status(self) -> str:
        """Get launchd service status on macOS.

        Returns:
            Status string
        """
        try:
            plist_file = Path.home() / "Library" / "LaunchAgents" / "com.withings.exporter.plist"

            if not plist_file.exists():
                return "Not installed"

            result = subprocess.run(
                ['launchctl', 'list', 'com.withings.exporter'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return "Running"
            else:
                return "Installed but not running"

        except Exception as e:
            return f"Error checking status: {e}"

    def _get_systemd_status(self) -> str:
        """Get systemd service status on Linux.

        Returns:
            Status string
        """
        try:
            result = subprocess.run(
                ['systemctl', '--user', 'is-active', 'withings-exporter.timer'],
                capture_output=True,
                text=True
            )

            return result.stdout.strip()

        except Exception as e:
            return f"Error checking status: {e}"
