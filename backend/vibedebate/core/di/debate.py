from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from vibedebate.ai.usage import LoggedAIProvider
from vibedebate.ai.analysis import MessageAnalyzer
from vibedebate.ai.tasks import TemplateMessageAnalyzer
from vibedebate.services.debate.analysis import AnalysisService
import httpx
from dishka import Provider, Scope, provide
from vibedebate.core.config import create_ai_settings, AISettings
from vibedebate.ai.contracts import AIProvider
from vibedebate.ai.deepseek import DeepSeekProvider
from vibedebate.ai.debate import DebateIntelligence, TemplateDebateIntelligence
from vibedebate.services.debate.service import DebateService


class DebateProvider(Provider):
    settings = provide(staticmethod(create_ai_settings), scope=Scope.APP)
    intelligence = provide(
        TemplateDebateIntelligence, provides=DebateIntelligence, scope=Scope.APP
    )
    service = provide(DebateService, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def ai(
        self,
        settings: AISettings,
        client: httpx.AsyncClient,
        factory: async_sessionmaker[AsyncSession],
    ) -> AIProvider:
        return LoggedAIProvider(
            DeepSeekProvider(settings, client),
            factory,
            provider="deepseek",
            model=settings.deepseek_model,
        )

    @provide(scope=Scope.APP)
    def analyzer(
        self,
        provider: AIProvider,
        settings: AISettings,
    ) -> MessageAnalyzer:
        return TemplateMessageAnalyzer(TemplateDebateIntelligence(provider, settings))

    @provide(scope=Scope.APP)
    async def analyses(
        self,
        factory: async_sessionmaker[AsyncSession],
        analyzer: MessageAnalyzer,
    ) -> AsyncIterator[AnalysisService]:
        service = AnalysisService(factory, analyzer)
        yield service
        await service.close()
