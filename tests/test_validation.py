from pathlib import Path

from hybrid_pipeline.pipeline.analysis import analyze_semantics
from hybrid_pipeline.pipeline.generation import generate_python
from hybrid_pipeline.pipeline.parsing import parse_procedure
from hybrid_pipeline.pipeline.validation import validate_python

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_generated_annex_b_passes_ast_parse():
    sql = (FIXTURES / "annex_b_fn_saldo_cliente.sql").read_text(encoding="utf-8")
    parsed = parse_procedure(sql)
    analysis = analyze_semantics(sql, parsed)
    gen = generate_python(sql, parsed, analysis, schema_context=None)
    validation = validate_python(gen["generated_code"])
    assert validation["ast_parse_ok"]
    assert validation["valid"]
