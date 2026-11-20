# -*- coding: utf-8 -*-
"""统一响应与异常处理。"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class BizError(Exception):
    """业务异常：code/message/status_code/data 统一输出。"""

    def __init__(self, code: int, message: str, status_code: int = 200, data=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data
        super().__init__(message)


def ok(data=None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


def fail(code: int, message: str, data=None, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": code, "message": message, "data": data})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizError)
    async def biz_error_handler(request: Request, exc: BizError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "data": exc.data},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        msg = f"参数错误：{first.get('loc', '')} {first.get('msg', '')}"
        return JSONResponse(status_code=200, content={"code": 10001, "message": msg, "data": None})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"code": 50000, "message": f"服务器内部错误：{exc}", "data": None},
        )
