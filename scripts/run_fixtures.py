"""Executa pipeline sobre Anexos B–F e grava em outputs/."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from hybrid_pipeline.graph.build import graph


async def main() -> None:
    root = Path(__file__).resolve().parents[1]
    fixtures = root / "fixtures"
    outputs = root / "outputs"
    outputs.mkdir(exist_ok=True)
    schema = (fixtures / "annex_a_schema.sql").read_text(encoding="utf-8")

    for sql_file in sorted(fixtures.glob("annex_[b-f]*.sql")):
        source = sql_file.read_text(encoding="utf-8")
        result = await graph.ainvoke(
            {"source_code": source, "schema_context": schema},
        )
        stem = sql_file.stem
        py_path = outputs / f"{stem}.py"
        report_path = outputs / f"{stem}_report.json"

        code = result.get("generated_code") or ""
        py_path.write_text(code, encoding="utf-8")
        report_path.write_text(
            json.dumps(result.get("report") or {}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"{stem}: status={result.get('status')} -> {py_path.name}")

    print(f"Outputs em {outputs}")


if __name__ == "__main__":
    asyncio.run(main())
