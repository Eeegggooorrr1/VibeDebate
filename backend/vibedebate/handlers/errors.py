from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from vibedebate.core.exceptions import AppError


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    error = {"code": exc.code, "message": exc.message}
    if exc.extra is not None:
        error["extra"] = exc.extra
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder({"error": error}),
        headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
    )
