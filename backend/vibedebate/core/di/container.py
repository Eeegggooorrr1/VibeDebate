from dishka import AsyncContainer, make_async_container
from dishka.integrations.fastapi import FastapiProvider
from .debate import DebateProvider
from .config import ConfigProvider
from .infrastructure import InfrastructureProvider
from .application import ApplicationProvider
from .authentication import AuthenticationProvider


def build_container() -> AsyncContainer:
    return make_async_container(
        ConfigProvider(),
        InfrastructureProvider(),
        ApplicationProvider(),
        DebateProvider(),
        AuthenticationProvider(),
        FastapiProvider(),
    )
