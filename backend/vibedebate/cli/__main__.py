import asyncio
import typer
from vibedebate.core.di.container import build_container
from vibedebate.cli.bootstrap.seed_service import SeedService

app = typer.Typer()


async def load() -> None:
    container = build_container()
    try:
        async with container() as request:
            await (await request.get(SeedService)).load_data()
    finally:
        await container.close()


@app.command()
def seed() -> None:
    asyncio.run(load())


def main() -> None:
    app()


if __name__ == "__main__":
    main()
