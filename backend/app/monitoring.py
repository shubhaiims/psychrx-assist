from __future__ import annotations

import os


def init_sentry() -> None:
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        return

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

    sentry_sdk.init(
        dsn=dsn,
        integrations=[FastApiIntegration(), StarletteIntegration()],
        traces_sample_rate=traces_sample_rate,
        send_default_pii=False,
        environment=(
            os.getenv("SENTRY_ENVIRONMENT")
            or os.getenv("VERCEL_ENV")
            or os.getenv("ENVIRONMENT")
            or "development"
        ),
        release=os.getenv("VERCEL_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT_SHA"),
    )
