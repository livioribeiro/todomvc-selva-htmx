from typing import Annotated as A

from asgikit.requests import Request
from asgikit.responses import respond_text
from pydantic import BaseModel
from selva import di, web
from selva.ext.templates.jinja import Template

from application.model import Todo
from application.service import TodoService


class TodoDTO(BaseModel):
    id: int = 0
    title: str
    completed: bool = False


class TodoCompleteDTO(BaseModel):
    completed: bool = False


@web.controller
class Controller:
    template: A[Template, di.Inject]
    service: A[TodoService, di.Inject]

    async def get_context(self, request: Request) -> dict:
        todo_filter = request.headers.get("x-filter", "all")

        if todo_filter == "active":
            filtered_todos = await self.service.get_active()
        elif todo_filter == "completed":
            filtered_todos = await self.service.get_completed()
        else:
            filtered_todos = await self.service.get_all()

        todo_count = await self.service.count()
        active_todo_count = await self.service.count(is_completed=False)
        completed_todo_count = await self.service.count(is_completed=True)

        return {
            "todo_count": todo_count,
            "active_todo_count": active_todo_count,
            "completed_todo_count": completed_todo_count,
            "todos": filtered_todos,
            "filter": todo_filter or "all",
        }

    async def htmx_response(
        self, request: Request, template: str | None, templates_oob: list[str] = None
    ):
        assert template or templates_oob, "template or templates_oob must be set"
        context = await self.get_context(request)
        context["oob"] = True

        output = await self.template.render(template, context) + "\n"
        output += "\n".join(
            [await self.template.render(name, context) for name in templates_oob]
        )

        request.response.headers["Content-Type"] = "text/html"
        await respond_text(request.response, output)

    @web.get
    async def index(
        self,
        request: Request,
        hx_request: A[str, web.FromHeader("HX-Request")] = None,
    ):
        if hx_request:
            await self.htmx_response(
                request,
                "components/filters.jinja",
                ["components/main.jinja"],
            )
        else:
            context = await self.get_context(request)
            await self.template.respond(request.response, "index.jinja", context)

    @web.post("todo")
    async def new_todo(self, request: Request, dto: TodoDTO):
        todo = Todo(title=dto.title, is_completed=dto.completed)
        await self.service.save(todo)

        await self.htmx_response(
            request,
            "components/main.jinja",
            ["components/footer.jinja"],
        )

    @web.put("todo/:todo_id")
    async def edit_todo(
        self, request: Request, dto: TodoDTO, todo_id: A[int, web.FromPath]
    ):
        await self.service.edit(todo_id, dto.title)
        await respond_text(request.response, dto.title)

    @web.post("todo/:todo_id/complete")
    async def complete_todo(
        self, request: Request, dto: TodoCompleteDTO, todo_id: A[int, web.FromPath]
    ):
        await self.service.complete(todo_id, dto.completed)

        await self.htmx_response(
            request,
            "components/main.jinja",
            ["components/footer.jinja"],
        )

    @web.post("todo/complete_all")
    async def complete_all(self, request: Request, dto: TodoCompleteDTO):
        await self.service.complete_all(dto.completed)

        await self.htmx_response(
            request,
            "components/main.jinja",
            ["components/header.jinja", "components/footer.jinja"],
        )

    @web.delete("todo/:todo_id")
    async def delete_todo(self, request: Request, todo_id: A[int, web.FromPath]):
        await self.service.delete(todo_id)

        await self.htmx_response(
            request,
            "components/main.jinja",
            ["components/footer.jinja"],
        )

    @web.delete("todo/completed")
    async def delete_completed(self, request: Request):
        await self.service.delete_completed()

        await self.htmx_response(
            request,
            "components/main.jinja",
            ["components/footer.jinja"],
        )
