"""Command-line interface for Withings Exporter."""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import click

from . import __version__
from .auth import get_auth_manager
from .config import get_config
from .export import DataExporter
from .fetcher import WithingsDataFetcher
from .scheduler import SyncScheduler
from .storage import HealthDataStorage

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__)
@click.option('--config', type=click.Path(), help='Path to config file')
@click.pass_context
def main(ctx, config):
    """Withings Health Data Exporter - Fetch and export your Withings health data."""
    ctx.ensure_object(dict)
    ctx.obj['config'] = get_config(config)
    ctx.obj['config'].setup_logging()


@main.command()
@click.pass_context
def setup(ctx):
    """Initial setup and OAuth authorization."""
    config = ctx.obj['config']

    click.echo("=" * 60)
    click.echo("Withings Health Data Exporter - Setup")
    click.echo("=" * 60)
    click.echo()

    # Check if configuration exists
    if not config.client_id or not config.client_secret:
        click.echo("No API credentials found. Let's configure them now.")
        click.echo()
        click.echo("To get your API credentials:")
        click.echo("1. Go to https://developer.withings.com/")
        click.echo("2. Create a developer account (or login)")
        click.echo("3. Create a new application (select 'Public API')")
        click.echo("4. Copy your Client ID and Client Secret")
        click.echo()

        client_id = click.prompt("Enter your Client ID")
        client_secret = click.prompt("Enter your Client Secret", hide_input=True)
        callback_uri = click.prompt("Enter callback URI", default="http://localhost:8080")

        # Save credentials to .env file
        env_file = config.DEFAULT_ENV_FILE
        env_content = f"""# Withings API Credentials
# Get these from https://developer.withings.com/
WITHINGS_CLIENT_ID={client_id}
WITHINGS_CLIENT_SECRET={client_secret}
WITHINGS_CALLBACK_URI={callback_uri}
"""
        with open(env_file, 'w') as f:
            f.write(env_content)

        # Set secure file permissions (read/write for owner only)
        env_file.chmod(0o600)

        click.echo()
        click.echo(f"✓ Credentials saved to {env_file}")
        click.echo()

        # Reload environment variables
        import os
        os.environ['WITHINGS_CLIENT_ID'] = client_id
        os.environ['WITHINGS_CLIENT_SECRET'] = client_secret
        os.environ['WITHINGS_CALLBACK_URI'] = callback_uri

    # Perform OAuth authorization
    click.echo("Starting OAuth authorization...")
    click.echo()

    auth_manager = get_auth_manager(
        config.client_id,
        config.client_secret,
        config.callback_uri,
        config.credentials_file
    )

    try:
        auth_manager.authorize()
        click.echo("✓ Authorization successful!")
        click.echo()
        click.echo("You're all set! You can now:")
        click.echo("  - Run 'withings-exporter sync --start-date 2010-01-01' to fetch all history")
        click.echo("  - Run 'withings-exporter sync' for incremental updates")
        click.echo("  - Run 'withings-exporter status' to check sync status")
        click.echo("  - Run 'withings-exporter export' to export data to JSON")
        click.echo("  - Run 'withings-exporter schedule install' to enable automatic syncing")
        click.echo()

    except Exception as e:
        click.echo(f"✗ Authorization failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--days', type=int, help='Fetch data from last N days')
@click.option('--start-date', type=click.DateTime(), help='Start date (YYYY-MM-DD). Use early date (e.g., 2010-01-01) for full history')
@click.option('--end-date', type=click.DateTime(), help='End date (YYYY-MM-DD)')
@click.pass_context
def sync(ctx, days, start_date, end_date):
    """Sync health data from Withings API.

    Examples:
      withings-exporter sync                           # Incremental sync (new data only)
      withings-exporter sync --days 30                 # Last 30 days
      withings-exporter sync --start-date 2010-01-01   # All history from 2010
      withings-exporter sync --start-date 2024-01-01 --end-date 2024-12-31
    """
    config = ctx.obj['config']

    # Check authorization
    auth_manager = get_auth_manager(
        config.client_id,
        config.client_secret,
        config.callback_uri,
        config.credentials_file
    )

    if not auth_manager.is_authorized():
        click.echo("Not authorized. Please run 'withings-exporter setup' first.", err=True)
        sys.exit(1)

    # Determine date range
    if days:
        start_date = datetime.now() - timedelta(days=days)
        click.echo(f"Fetching data from last {days} days...")
    elif start_date:
        if end_date:
            click.echo(f"Fetching data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
        else:
            click.echo(f"Fetching data from {start_date.strftime('%Y-%m-%d')} to now...")
    else:
        # Incremental sync
        click.echo("Fetching new data since last sync...")

    # Initialize storage and fetcher
    storage = HealthDataStorage(config.database_path)
    credentials = auth_manager.get_credentials()
    fetcher = WithingsDataFetcher(credentials, storage)

    # Fetch data
    try:
        with click.progressbar(
            length=5,
            label='Syncing data',
            show_eta=False
        ) as bar:
            fetcher.fetch_all_data(
                start_date=start_date,
                end_date=end_date,
                data_types=config.enabled_data_types
            )
            bar.update(5)

        # Show statistics
        stats = storage.get_statistics()
        click.echo()
        click.echo("✓ Sync completed!")
        click.echo()
        click.echo("Database statistics:")
        click.echo(f"  Measurements: {stats['measurements']:,}")
        click.echo(f"  Activity records: {stats['activity_summary']:,}")
        click.echo(f"  Sleep sessions: {stats['sleep_summary']:,}")
        click.echo(f"  Heart rate records: {stats['heart_rate']:,}")
        click.echo()

    except Exception as e:
        click.echo(f"✗ Sync failed: {e}", err=True)
        logger.exception("Sync error")
        sys.exit(1)
    finally:
        storage.close()


@main.command()
@click.option('--format', type=click.Choice(['json', 'csv']), default='json', help='Export format')
@click.option('--output', type=click.Path(), help='Output file path')
@click.option('--start-date', type=click.DateTime(), help='Start date (YYYY-MM-DD)')
@click.option('--end-date', type=click.DateTime(), help='End date (YYYY-MM-DD)')
@click.pass_context
def export(ctx, format, output, start_date, end_date):
    """Export health data to file."""
    config = ctx.obj['config']

    # Initialize storage and exporter
    storage = HealthDataStorage(config.database_path)
    exporter = DataExporter(storage, config.export_path)

    try:
        if format == 'json':
            output_path = exporter.export_to_json(
                output_file=output,
                start_date=start_date,
                end_date=end_date,
                include_metadata=config.get('export.format.include_metadata', True),
                pretty_print=config.get('export.format.pretty_print', True)
            )
            click.echo(f"✓ Data exported to {output_path}")

        elif format == 'csv':
            # Export to multiple CSV files
            if not output:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_prefix = f"export_{timestamp}"
                output_dir = None
            else:
                output_path = Path(output)
                output_prefix = output_path.stem
                output_dir = output_path.parent if output_path.parent != Path('.') else None
                if output_dir:
                    output_dir.mkdir(parents=True, exist_ok=True)

            def csv_path(suffix: str) -> str:
                filename = f"{output_prefix}_{suffix}.csv"
                if output_dir:
                    return str(output_dir / filename)
                return filename

            measurements_file = exporter.export_measurements_csv(
                csv_path("measurements"),
                start_date,
                end_date
            )
            activity_file = exporter.export_activity_csv(
                csv_path("activity"),
                start_date,
                end_date
            )
            sleep_file = exporter.export_sleep_csv(
                csv_path("sleep"),
                start_date,
                end_date
            )
            heart_rate_file = exporter.export_heart_rate_csv(
                csv_path("heart_rate"),
                start_date,
                end_date
            )

            click.echo("✓ Data exported to CSV files:")
            click.echo(f"  {measurements_file}")
            click.echo(f"  {activity_file}")
            click.echo(f"  {sleep_file}")
            click.echo(f"  {heart_rate_file}")

    except Exception as e:
        click.echo(f"✗ Export failed: {e}", err=True)
        logger.exception("Export error")
        sys.exit(1)
    finally:
        storage.close()


@main.command()
@click.pass_context
def status(ctx):
    """Show sync status and statistics."""
    config = ctx.obj['config']

    click.echo("=" * 60)
    click.echo("Withings Health Data Exporter - Status")
    click.echo("=" * 60)
    click.echo()

    # Check authorization
    auth_manager = get_auth_manager(
        config.client_id,
        config.client_secret,
        config.callback_uri,
        config.credentials_file
    )

    if auth_manager.is_authorized():
        click.echo("✓ Authorized")
    else:
        click.echo("✗ Not authorized (run 'withings-exporter setup')")

    click.echo()

    # Database statistics
    if config.database_path.exists():
        storage = HealthDataStorage(config.database_path)

        stats = storage.get_statistics()
        click.echo("Database Statistics:")
        click.echo(f"  Database: {config.database_path}")
        click.echo(f"  Measurements: {stats['measurements']:,}")
        click.echo(f"  Activity records: {stats['activity_summary']:,}")
        click.echo(f"  Sleep sessions: {stats['sleep_summary']:,}")
        click.echo(f"  Heart rate records: {stats['heart_rate']:,}")
        click.echo()

        # Sync state
        click.echo("Last Sync:")
        for data_type in ['measurements', 'activity', 'sleep']:
            sync_state = storage.get_sync_state(data_type)
            if sync_state:
                last_sync = sync_state.get('last_sync')
                status_str = sync_state.get('status', 'unknown')
                click.echo(f"  {data_type.capitalize()}: {last_sync} ({status_str})")
            else:
                click.echo(f"  {data_type.capitalize()}: Never synced")

        storage.close()
    else:
        click.echo("No database found. Run 'withings-exporter sync' to fetch data.")

    click.echo()

    # Scheduler status
    scheduler = SyncScheduler(config.sync_interval)
    scheduler_status = scheduler.get_status()
    click.echo(f"Scheduler: {scheduler_status}")
    click.echo()


@main.group()
def schedule():
    """Manage automatic syncing schedule."""
    pass


@schedule.command('install')
@click.pass_context
def schedule_install(ctx):
    """Install automatic sync schedule."""
    config = ctx.obj['config']

    # Get the path to the withings-exporter command
    import shutil
    script_path = shutil.which('withings-exporter')

    if not script_path:
        click.echo("✗ Could not find withings-exporter command in PATH", err=True)
        click.echo("Make sure the package is installed properly.", err=True)
        sys.exit(1)

    scheduler = SyncScheduler(config.sync_interval)

    click.echo(f"Installing automatic sync (every {config.sync_interval} seconds)...")

    if scheduler.install_schedule(script_path):
        click.echo("✓ Automatic sync installed successfully!")
        click.echo()
        click.echo(f"Logs will be written to: {config.DEFAULT_LOG_PATH}/sync.log")
    else:
        click.echo("✗ Failed to install automatic sync", err=True)
        sys.exit(1)


@schedule.command('uninstall')
@click.pass_context
def schedule_uninstall(ctx):
    """Uninstall automatic sync schedule."""
    config = ctx.obj['config']

    scheduler = SyncScheduler(config.sync_interval)

    click.echo("Uninstalling automatic sync...")

    if scheduler.uninstall_schedule():
        click.echo("✓ Automatic sync uninstalled successfully!")
    else:
        click.echo("✗ Failed to uninstall automatic sync", err=True)
        sys.exit(1)


@schedule.command('status')
@click.pass_context
def schedule_status(ctx):
    """Check automatic sync status."""
    config = ctx.obj['config']

    scheduler = SyncScheduler(config.sync_interval)
    status = scheduler.get_status()

    click.echo(f"Scheduler status: {status}")
    click.echo(f"Sync interval: {config.sync_interval} seconds ({config.sync_interval // 3600} hours)")


@main.command()
@click.pass_context
def config_show(ctx):
    """Show current configuration."""
    config = ctx.obj['config']

    click.echo("=" * 60)
    click.echo("Configuration")
    click.echo("=" * 60)
    click.echo()
    click.echo(f"Config file: {config.config_path}")
    click.echo(f"Database: {config.database_path}")
    click.echo(f"Export path: {config.export_path}")
    click.echo(f"Credentials: {config.credentials_file}")
    click.echo(f"Log file: {config.log_file}")
    click.echo()
    click.echo(f"Sync interval: {config.sync_interval} seconds")
    click.echo(f"Enabled data types: {', '.join(k for k, v in config.enabled_data_types.items() if v)}")
    click.echo()


if __name__ == '__main__':
    main()
