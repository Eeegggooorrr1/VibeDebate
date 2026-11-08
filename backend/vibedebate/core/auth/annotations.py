from typing import Annotated
from fastapi import Depends
from vibedebate.core.auth.guards import RequireUser
from vibedebate.core.auth.roles import Role
from vibedebate.schemas.internal.user import CurrentUser

AuthenticatedUser = Annotated[CurrentUser, Depends(RequireUser())]
AdminUser = Annotated[CurrentUser, Depends(RequireUser(Role.ADMIN))]
