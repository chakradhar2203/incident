"""
RCA Assistant – Entry point
Run with:  python run.py
Or:        uvicorn app.main:app --reload --port 8000
"""
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    import uvicorn
    from app.config import get_settings

    settings = get_settings()

    print("\n" + "=" * 60)
    print("  RCA Assistant – AI Incident Triage")
    print("=" * 60)
    print(f"  URL:           http://localhost:{settings.app_port}")
    print(f"  Analysis Mode: {settings.analysis_mode}")
    print(f"  Claude API:    {'[OK] Configured' if settings.claude_api_key else '[--] Not set (local mode)'}")
    print(f"  Firebase:      {'[OK] Path set' if settings.firebase_service_account_path else '[--] In-memory only'}")
    print(f"  SN Write-back: {'[ON] Enabled' if settings.servicenow_writeback_enabled else '[OFF] Disabled'}")
    print("=" * 60 + "\n")

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
        log_level="info",
    )
