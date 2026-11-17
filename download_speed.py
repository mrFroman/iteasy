#!/usr/bin/env python3
"""Последовательная загрузка URL и оценка скорости скачивания."""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

REQUEST_COUNT = 10
REQUEST_TIMEOUT_SEC = 60
# 1 МБ = 1024² байт
BYTES_PER_MB = 1024 * 1024
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

console = Console(stderr=False)


@dataclass(frozen=True)
class DownloadResult:
    index: int
    elapsed_sec: float
    size_bytes: int

    @property
    def size_mb(self) -> float:
        return self.size_bytes / BYTES_PER_MB

    @property
    def speed_mb_s(self) -> float:
        if self.elapsed_sec <= 0:
            return 0.0
        return self.size_mb / self.elapsed_sec


def validate_url(url: str) -> str:
    """Проверяет, что URL — http(s) с хостом."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL должен начинаться с http:// или https://")
    if not parsed.netloc:
        raise ValueError("В URL отсутствует хост")
    return url


def download_once(url: str) -> tuple[float, int]:
    """Скачивает URL целиком. Возвращает (секунды, байты)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SEC) as response:
        data = response.read()
    elapsed = time.perf_counter() - started
    return elapsed, len(data)


def build_results_table(results: list[DownloadResult]) -> Table:
    table = Table(
        title="Результаты запросов",
        show_header=True,
        header_style="bold cyan",
        border_style="bright_black",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Время, с", justify="right")
    table.add_column("Объём, МБ", justify="right")
    table.add_column("Скорость, МБ/с", justify="right")

    for item in results:
        table.add_row(
            str(item.index),
            f"{item.elapsed_sec:.3f}",
            f"{item.size_mb:.3f}",
            f"{item.speed_mb_s:.3f}",
        )
    return table


def print_summary(results: list[DownloadResult]) -> None:
    total_bytes = sum(item.size_bytes for item in results)
    total_seconds = sum(item.elapsed_sec for item in results)
    avg_seconds = total_seconds / len(results)
    total_mb = total_bytes / BYTES_PER_MB
    speed_mb_s = (total_bytes / total_seconds) / BYTES_PER_MB if total_seconds else 0.0

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Среднее время запроса", f"{avg_seconds:.3f} с")
    summary.add_row("Общий объём данных", f"{total_mb:.3f} МБ ({total_bytes:,} байт)")
    summary.add_row(
        "Скорость скачивания",
        Text(f"{speed_mb_s:.3f} МБ/с", style="bold green"),
    )

    console.print()
    console.print(
        Panel(
            summary,
            title="[bold]Итог[/bold]",
            border_style="green",
            padding=(1, 2),
        )
    )


def run(url: str) -> int:
    console.print(
        Panel(
            Text.from_markup(
                f"[bold]URL[/bold]: {url}\n"
                f"[bold]Запросов[/bold]: {REQUEST_COUNT} (последовательно)\n"
                f"[bold]Таймаут[/bold]: {REQUEST_TIMEOUT_SEC} с"
            ),
            title="[bold blue]Download Speed[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )
    )

    results: list[DownloadResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Загрузка", total=REQUEST_COUNT)

        for index in range(1, REQUEST_COUNT + 1):
            progress.update(task_id, description=f"Запрос #{index}")
            try:
                elapsed, size = download_once(url)
            except urllib.error.HTTPError as exc:
                console.print(
                    f"[bold red]HTTP-ошибка[/bold red] на запросе #{index}: "
                    f"{exc.code} {exc.reason}"
                )
                return 1
            except urllib.error.URLError as exc:
                console.print(
                    f"[bold red]Ошибка сети[/bold red] на запросе #{index}: {exc.reason}"
                )
                return 1
            except TimeoutError:
                console.print(
                    f"[bold red]Таймаут[/bold red] на запросе #{index} "
                    f"({REQUEST_TIMEOUT_SEC} с)"
                )
                return 1

            results.append(
                DownloadResult(index=index, elapsed_sec=elapsed, size_bytes=size)
            )
            progress.advance(task_id)

    console.print()
    console.print(build_results_table(results))
    print_summary(results)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Делает 10 последовательных запросов к URL, "
            "считает среднее время, объём данных и скорость (МБ/с)."
        )
    )
    parser.add_argument(
        "url",
        help="Адрес ресурса (например, тяжёлая картинка)",
    )
    args = parser.parse_args()

    try:
        url = validate_url(args.url)
    except ValueError as exc:
        console.print(f"[bold red]Некорректный URL:[/bold red] {exc}")
        return 2

    try:
        return run(url)
    except KeyboardInterrupt:
        console.print("\n[yellow]Прервано пользователем.[/yellow]")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
