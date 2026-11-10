from dishka import Provider, Scope, provide
from starlette.requests import Request
from vibedebate.services.user.exceptions import InvalidAccessTokenError
from vibedebate.services.user.tokens import TokenVerifier
from vibedebate.schemas.internal.user import CurrentUser


class AuthenticationProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def get_current_user(
        self,
        request: Request,
        verifier: TokenVerifier,
    ) -> CurrentUser:
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")

        if scheme.lower() != "bearer" or not token or len(token) > 16384:
            raise InvalidAccessTokenError()

        return await verifier.verify_access_token(token)
