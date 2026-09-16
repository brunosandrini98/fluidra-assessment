import logging
from functools import cache

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pool_qa.contract import AskRequest, AskResponse, ErrorResponse
from pool_qa.graph import RequestTimeout, default_agents, make_ask
from pool_qa.llm import ProviderError
from pool_qa.settings import Settings

logging.basicConfig(format="%(message)s")
logging.getLogger("pool_qa").setLevel(logging.INFO)

app = FastAPI(title="Pool equipment QA")


@cache
def get_ask():
    settings = Settings()
    return make_ask(default_agents(settings), settings)


def _error(status: int, error: str, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=ErrorResponse(error=error, detail=detail).model_dump())


@app.exception_handler(RequestValidationError)
async def _invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
    detail = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
    return _error(422, "invalid_request", detail)


@app.exception_handler(ProviderError)
async def _provider_error(request: Request, exc: ProviderError) -> JSONResponse:
    return _error(502, "provider_error", str(exc))


@app.exception_handler(RequestTimeout)
async def _timeout(request: Request, exc: RequestTimeout) -> JSONResponse:
    return _error(504, "timeout", str(exc))


@app.post("/ask", response_model=AskResponse)
async def post_ask(request: AskRequest, run=Depends(get_ask)) -> AskResponse:
    return await run(request)
