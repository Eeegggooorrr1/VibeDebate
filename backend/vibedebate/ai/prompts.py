

import json
from typing import Any
from jinja2 import Environment, PackageLoader, StrictUndefined
from vibedebate.ai.contracts import AIMessage

ENV = Environment(
    loader=PackageLoader("vibedebate.ai", "templates"),
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
ENV.policies["json.dumps_kwargs"] = {"sort_keys": True, "ensure_ascii": False}

TASKS = {
    name: f"tasks/{name}/main.jinja"
    for name in (
        "plan",
        "attack",
        "defense",
        "opponent",
        "analysis",
        "summary",
        "suggest",
    )
}
PERSONAS = {
    name: f"personas/{name}.jinja"
    for name in ("socratic", "formal_logician", "empirical_skeptic")
}
DIFFICULTIES = {level: f"difficulties/{level}.jinja" for level in (1, 2, 3)}
DIRECTIONS = {name: f"directions/{name}.jinja" for name in ("attack", "defense")}


def plan_task(
    count: int,
) -> str:
    return render_task("plan", count=count)


def structured_messages(
    task: str,
    schema: dict[str, Any],
    context: dict[str, Any],
) -> list[AIMessage]:
    return [
        AIMessage(
            role="system",
            content=task
            + "\n"
            + ENV.get_template("components/structured_output.jinja").render(
                schema=schema
            ),
        ),
        AIMessage(
            role="user",
            content=json.dumps(context, ensure_ascii=False, separators=(",", ":")),
        ),
    ]


def render_task(
    name: str,
    **variables: Any,
) -> str:
    if name not in TASKS:
        raise ValueError(f"Unknown prompt task: {name}")

    if name in ("opponent", "defense"):
        context = variables["context"]
        style = context.get("persona", {}).get("style", "socratic")
        difficulty = context.get("difficulty", 1)

        if difficulty not in DIFFICULTIES:
            raise ValueError("Unsupported opponent difficulty")

        variables.update(
            persona_template=PERSONAS.get(style, "personas/generic.jinja"),
            difficulty_template=DIFFICULTIES[difficulty],
        )

        if name == "opponent":
            side = context.get("side")

            if side not in DIRECTIONS:
                raise ValueError("Unsupported chat direction")

            variables["direction_template"] = DIRECTIONS[side]

    return ENV.get_template(TASKS[name]).render(**variables).strip()


def opponent_instruction(
    context: dict[str, Any],
) -> AIMessage:
    return AIMessage(role="system", content=render_task("opponent", context=context))
