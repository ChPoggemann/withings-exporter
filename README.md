# Withings Health Data Exporter

A Python tool to automatically fetch and export health data from Withings API for personal use and LLM analysis.

## Features

- **Comprehensive Data Export**: Fetch all your Withings health data including:
  - Body measurements (weight, body composition, vitals)
  - Activity data (steps, distance, calories)
  - Sleep data (duration, quality, stages, breathing)
  - Heart rate and blood pressure
  - And more...

- **Multiple Export Formats**:
  - JSON (optimized for LLM consumption)
  - CSV (for spreadsheet analysis)
  - SQLite database (for querying)

- **Automated Syncing**:
  - Configurable sync intervals (hourly by default)
  - Cross-platform scheduling (macOS launchd, Linux systemd)
  - Incremental updates (only fetch new data)

- **Historical Data Import**: Import your complete Withings history on first run

## Prerequisites

1. **Withings Developer Account**:
   - Go to [https://developer.withings.com/](https://developer.withings.com/)
   - Create a developer account
   - Create a new application (select "Public API" integration)
   - Note your Client ID and Client Secret

2. **Python 3.9+**

## Installation

Using `uv` (recommended):

```bash
cd /path/to/withings-exporter
uv pip install -e .
```

Or using `pip`:

```bash
cd /path/to/withings-exporter
pip install -e .
```

## Quick Start

### 1. Get API Credentials

First, get your Withings API credentials:
1. Go to [https://developer.withings.com/](https://developer.withings.com/)
2. Create a developer account (or login)
3. Create a new application (select "Public API" integration)
4. Note your Client ID and Client Secret

### 2. Initial Setup

Run the setup command to configure your API credentials and authorize access:

```bash
withings-exporter setup
```

This will:
- Prompt for your Withings API credentials
- Save them securely to `~/.withings/.env`
- Open your browser for OAuth authorization
- Save OAuth tokens to `~/.withings/credentials.json`

**Alternative: Manual Setup**

You can also create `~/.withings/.env` manually:

```bash
mkdir -p ~/.withings
cat > ~/.withings/.env << 'EOF'
WITHINGS_CLIENT_ID=your_client_id_here
WITHINGS_CLIENT_SECRET=your_client_secret_here
WITHINGS_CALLBACK_URI=http://localhost:8080
EOF
chmod 600 ~/.withings/.env
```

Then run `withings-exporter setup` to complete OAuth authorization.

### 3. Sync Your Data

Fetch your health data from Withings:

```bash
# Sync all historical data (specify a date before your first Withings device)
withings-exporter sync --start-date 2010-01-01

# Sync last 30 days
withings-exporter sync --days 30

# Sync specific date range
withings-exporter sync --start-date 2024-01-01 --end-date 2024-12-31

# Incremental sync (only new data since last sync)
withings-exporter sync
```

### 4. Export Data

Export your data to JSON for LLM analysis:

```bash
# Export to JSON (default)
withings-exporter export

# Export to CSV
withings-exporter export --format csv

# Export specific date range
withings-exporter export --start-date 2024-01-01 --end-date 2024-12-31
```

### 5. Enable Automatic Syncing

Set up automatic hourly syncing:

```bash
withings-exporter schedule install
```

## Usage

### Commands

#### `setup`
Initial setup and OAuth authorization.

```bash
withings-exporter setup
```

#### `sync`
Sync health data from Withings API.

```bash
# Full historical sync (specify date before your first device)
withings-exporter sync --start-date 2010-01-01

# Sync last N days
withings-exporter sync --days 7

# Sync specific date range
withings-exporter sync --start-date 2024-01-01 --end-date 2024-12-31

# Incremental sync (default - only new data since last sync)
withings-exporter sync
```

#### `export`
Export health data to file.

```bash
# Export to JSON
withings-exporter export --format json

# Export to CSV
withings-exporter export --format csv

# Export to custom location
withings-exporter export --output ~/my-health-data.json

# Export specific date range
withings-exporter export --start-date 2024-01-01
```

#### `status`
Show sync status and database statistics.

```bash
withings-exporter status
```

#### `schedule`
Manage automatic syncing.

```bash
# Install automatic sync
withings-exporter schedule install

# Check scheduler status
withings-exporter schedule status

# Uninstall automatic sync
withings-exporter schedule uninstall
```

#### `config-show`
Show current configuration.

```bash
withings-exporter config-show
```

## Configuration

### API Credentials

API credentials are stored securely in `~/.withings/.env`:

```bash
WITHINGS_CLIENT_ID=your_client_id
WITHINGS_CLIENT_SECRET=your_client_secret
WITHINGS_CALLBACK_URI=http://localhost:8080
```

The setup command creates this file automatically, but you can also create it manually.

### Application Settings

Application settings are stored in `~/.withings/config.yaml`. You can customize:

### Sync Interval

```yaml
sync:
  interval: 3600  # seconds (3600 = 1 hour)
```

### Data Types

Enable/disable specific data types:

```yaml
sync:
  data_types:
    measurements: true
    activity: true
    sleep: true
    heart_rate: true
```

### Export Settings

```yaml
export:
  export_path: "~/.withings/exports/"
  format:
    include_metadata: true
    pretty_print: true
```

### Logging

```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  log_file: "~/.withings/logs/exporter.log"
  console: true
```

## File Locations

- **API Credentials**: `~/.withings/.env` (API keys - keep secure!)
- **OAuth Tokens**: `~/.withings/credentials.json`
- **Configuration**: `~/.withings/config.yaml`
- **Database**: `~/.withings/health_data.db`
- **Exports**: `~/.withings/exports/`
- **Logs**: `~/.withings/logs/`

## JSON Export Format

The JSON export is optimized for LLM consumption with a clear structure:

```json
{
  "export_metadata": {
    "export_time": "2026-01-10T12:00:00",
    "date_range": {
      "start": "2020-01-01",
      "end": "2026-01-10"
    },
    "data_types": ["measurements", "activity", "sleep"],
    "database_stats": {...}
  },
  "measurements": {
    "weight": [
      {"timestamp": "2026-01-10T08:00:00", "value": 75.5, "unit": "kg"},
      ...
    ],
    "body_fat": [...],
    ...
  },
  "activity": {
    "daily_summary": [...],
    "statistics": {...}
  },
  "sleep": {
    "sessions": [...],
    "statistics": {...}
  }
}
```

## Database Schema

Data is stored in SQLite with the following tables:

- `measurements`: Body measurements (weight, body composition, vitals)
- `activity_summary`: Daily activity summaries
- `activity_intraday`: Detailed intraday activity
- `sleep_summary`: Sleep session summaries
- `heart_rate`: Heart rate measurements
- `sync_state`: Sync state tracking

## Scheduling

### macOS (launchd)

The tool automatically creates a launchd service at:
```
~/Library/LaunchAgents/com.withings.exporter.plist
```

Manage with:
```bash
# View logs
tail -f ~/.withings/logs/sync.log

# Manually trigger
launchctl start com.withings.exporter
```

### Linux (systemd)

The tool automatically creates systemd user services:
```
~/.config/systemd/user/withings-exporter.service
~/.config/systemd/user/withings-exporter.timer
```

Manage with:
```bash
# Check status
systemctl --user status withings-exporter.timer

# View logs
journalctl --user -u withings-exporter.service -f

# Manually trigger
systemctl --user start withings-exporter.service
```

## Troubleshooting

### Authorization Issues

If you get authorization errors:

```bash
# Clear credentials and re-authorize
rm ~/.withings/credentials.json
withings-exporter setup
```

### Sync Failures

Check the logs:

```bash
tail -f ~/.withings/logs/exporter.log
```

Enable debug logging in `~/.withings/config.yaml`:

```yaml
logging:
  level: "DEBUG"
```

### Database Issues

The database file is at `~/.withings/health_data.db`. You can query it directly:

```bash
sqlite3 ~/.withings/health_data.db
```

## API Rate Limits

Withings API has a limit of 120 requests/minute. The tool respects this limit:

- Hourly sync uses ~5-10 API calls
- Historical import is chunked to avoid limits
- Incremental updates are efficient

## Privacy & Security

- All data is stored locally on your machine
- API credentials stored in `.env` file with restricted permissions (0600)
- OAuth tokens stored in `credentials.json` with restricted permissions (0600)
- No data is sent to third parties
- OAuth tokens are automatically refreshed
- `.env` file is excluded from git to prevent accidental credential exposure

## Development

### Project Structure

```
withings-exporter/
├── withings_exporter/
│   ├── __init__.py
│   ├── auth.py          # OAuth authentication
│   ├── config.py        # Configuration management
│   ├── storage.py       # SQLite database
│   ├── fetcher.py       # API data fetching
│   ├── export.py        # Data export
│   ├── scheduler.py     # Automated scheduling
│   └── cli.py           # CLI interface
├── tests/
├── requirements.txt
├── setup.py
├── config.yaml.template
└── README.md
```

### Running Tests

```bash
uv pip install -e ".[test]"
python -m pytest -q
```

## Contributing

Contributions are welcome! Please see `AGENTS.md` for contributor guidelines.

## Disclaimer

This project was developed with assistance from an AI agent. Please review changes carefully, especially around OAuth and data handling.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built against the official [Withings API](https://developer.withings.com/)
- Uses [Click](https://click.palletsprojects.com/) for CLI
- Data stored with SQLite

## Resources

- [Withings Developer Portal](https://developer.withings.com/)
- [Withings API Documentation](https://developer.withings.com/developer-guide/v3/)
- [Available Health Data Types](https://developer.withings.com/developer-guide/v3/data-api/all-available-health-data/)
