# Run PsychRx Assist on Your Laptop

This mode does not use Vercel. It runs both parts of the site on your own laptop:

- frontend website: `http://127.0.0.1:3000`
- backend API: `http://127.0.0.1:8000`

## Start

Double-click:

```text
START_LOCAL_WEBSITE.bat
```

Or run from PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-laptop.ps1
```

## Stop

Double-click:

```text
STOP_LOCAL_WEBSITE.bat
```

Or run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop-laptop.ps1
```

## Check Status

Double-click:

```text
STATUS_LOCAL_WEBSITE.bat
```

## First-Time Setup

If dependencies are missing, start with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-laptop.ps1 -Install -Rebuild
```

The scripts keep logs and process IDs in `.runtime/`, which is ignored by Git.
