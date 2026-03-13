from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_foundry.api import create_runtime
from agent_foundry.config import FoundryConfig
from agent_foundry.http_routes import ServerServices, build_api_router
from services.ai import AiService
from services.conversations import ConversationStore


def create_app(config: FoundryConfig) -> FastAPI:
    platform_service, service = create_runtime(config)
    services = ServerServices(
        platform_service=platform_service,
        service=service,
        ai_service=AiService(platform_service),
        conversation_store=ConversationStore(
            config.conversations_root,
            embeddings_root=config.embeddings_root,
        ),
    )

    app = FastAPI(title="{name} Server".format(name=config.app_name))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_api_router(services))

    setattr(app, "service", services.service)
    setattr(app, "platform_service", services.platform_service)
    setattr(app, "conversation_store", services.conversation_store)
    return app
