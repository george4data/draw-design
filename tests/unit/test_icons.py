"""Vendor icon catalog, spec checks, emission and lint (PRD §10.8)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ddraw.cli import main
from ddraw.doctor import _icons_check
from ddraw.errors import DDError
from ddraw.export import drawio_cli
from ddraw.icons import catalog
from ddraw.lint.runner import lint_text
from ddraw.pipeline import build
from ddraw.spec.validate import validate
from ddraw.theme.model import load_theme
from helpers import example


def codes(findings: list[Any]) -> dict[str, str]:
    return {f.code: f.severity for f in findings}


# ---------------------------------------------------------------- catalog


def test_catalog_families_are_verified() -> None:
    fams = catalog.families()
    assert {"aws4", "gcp", "gcp3", "azure2", "kubernetes"} <= set(fams)
    assert catalog.verified_with()
    assert fams["aws4"].recolor == "fill" and fams["gcp3"].recolor == "none"
    assert all(f.count > 0 for f in fams.values())


def test_lookup_and_search() -> None:
    lam = catalog.lookup("aws4:lambda")
    assert lam is not None and lam.kind == "icon" and "resIcon=mxgraph.aws4.lambda" in lam.style
    assert catalog.lookup("aws4:nope") is None and catalog.lookup("lambda") is None
    assert [e.id for e in catalog.search("postgres database", platform="aws", limit=2)] == [
        "aws4:aurora",
        "aws4:rds",
    ]
    assert catalog.search("s3 bucket", platform="aws")[0].id == "aws4:s3"
    assert catalog.search("cloud run", platform="gcp")[0].id == "gcp:cloud_run"
    assert catalog.search("vpc", platform="aws", kind="group")[0].id == "aws4:group_vpc"
    assert catalog.search("", platform="aws") == []


def test_suggest_did_you_mean() -> None:
    assert "aws4:lambda" in catalog.suggest("aws4:lamda")
    assert "aws4:lambda" in catalog.suggest("aws:lambda")  # unknown family, close name


def test_cell_style_strips_label_keys_and_recolours() -> None:
    lam = catalog.lookup("aws4:lambda")
    assert lam is not None
    style = catalog.cell_style(lam)
    assert "verticalLabelPosition" not in style and "fontColor" not in style and "points=" not in style
    assert "fillColor=#ED7100" in style and style.endswith("movable=0;resizable=0;")
    assert "fillColor=#4f5d75" in catalog.cell_style(lam, mono="#4f5d75")


def test_shape_key_reads_vendor_styles() -> None:
    assert catalog.shape_key({"shape": "mxgraph.aws4.resourceIcon", "resIcon": "mxgraph.aws4.sqs"}) == (
        "aws4",
        "sqs",
    )
    assert catalog.shape_key({"shape": "image", "image": "img/lib/azure2/databases/Azure_Cosmos_DB.svg"}) == (
        "azure2",
        "azure_cosmos_db",
    )
    assert ("aws4", "sqs") in catalog.known_keys() and ("azure2", "azure_cosmos_db") in catalog.known_keys()
    assert catalog.shape_key({"shape": "rect"}) is None


# ---------------------------------------------------------------- spec checks


def aws() -> dict[str, Any]:
    return example("architecture-aws")


def test_aws_example_is_clean() -> None:
    spec, findings = validate(aws())
    assert spec is not None and not [f for f in findings if f.severity != "info"]


@pytest.mark.parametrize(
    ("icon", "fix_part"),
    [("aws4:lamda", "aws4:lambda"), ("database", "planned"), ("aws4:group_vpc", "service icon")],
)
def test_bad_icon_ids_fail_with_a_fix(icon: str, fix_part: str) -> None:
    data = aws()
    data["nodes"][4]["icon"] = icon
    spec, findings = validate(data)
    assert spec is None
    bad = [f for f in findings if f.code == "LR-I001"]
    assert bad and bad[0].pointer == "/nodes/4/icon" and fix_part in (bad[0].fix or "")


def test_icons_only_on_types_that_use_them() -> None:
    data = example("flowchart")
    data["nodes"][1]["icon"] = "aws4:lambda"
    spec, findings = validate(data)
    assert spec is None and "SPEC-030" in codes(findings)


def test_zone_icons_are_planned() -> None:
    data = aws()
    data["zones"][1]["icon"] = "aws4:group_vpc"
    assert "SPEC-031" in codes(validate(data)[1])


def test_family_mixing_mono_and_partial_icons_warn() -> None:
    data = aws()
    data["iconStyle"] = "mono"
    data["nodes"][3]["icon"] = "gcp:cloud_run"
    data["nodes"][4]["icon"] = "gcp3:cloudrun"
    del data["nodes"][5]["icon"]
    data["nodes"][2]["tag"] = "EDGE"
    spec, findings = validate(data)
    assert spec is not None
    got = codes(findings)
    assert got["LR-I002"] == "warn"  # gcp + gcp3
    assert got["LR-I004"] == "warn"  # mono cannot recolour gcp / gcp3
    assert got["LR-I005"] == "warn"  # db lost its icon
    assert got["SPEC-032"] == "warn"  # tag and icon on gw


def test_sequence_participants_take_icons() -> None:
    data = example("sequence")
    data["sequence"]["participants"][1]["icon"] = "gcp:cloud_run"
    data["sequence"]["participants"][3]["icon"] = "gcp:cloud_run"
    data["sequence"]["participants"][2]["icon"] = "gcp:cloud_iam"
    result = build(data)
    assert result.ok
    assert result.xml.count('dd-role="icon"') == 3


# ---------------------------------------------------------------- emission and lint


def test_build_emits_icon_cells_and_lints_clean() -> None:
    result = build(aws())
    xml = result.xml
    assert result.ok and xml.count('dd-role="icon"') == 6
    assert 'dd-icon="aws4:lambda"' in xml and "resIcon=mxgraph.aws4.lambda" in xml
    assert 'dd-role="tag"' in xml  # Stripe has no icon and keeps its tag
    assert "align=left" in xml and "spacingLeft=46" in xml
    found = codes(result.findings)
    assert found.get("LR-I007") == "info" and "LR-T001" not in found


def test_mono_recolours_to_theme_muted() -> None:
    data = aws()
    data["iconStyle"] = "mono"
    result = build(data)
    muted = load_theme().c("muted")
    assert result.ok and "fillColor=#ED7100" not in result.xml
    assert f"fillColor={muted};" in result.xml and 'dd-icon-style="mono"' in result.xml


def test_icon_room_widens_nodes() -> None:
    plain, icons = build(example("architecture")).page, build(aws()).page
    assert icons.nodes["gw"].box.w > plain.nodes["gw"].box.w


def foreign(style: str) -> str:
    return (
        '<mxfile><diagram id="p" name="P"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        f'<mxCell id="a" style="{style}" vertex="1" parent="1"><mxGeometry x="0" y="0" width="48" height="48"'
        ' as="geometry"/></mxCell>'
        '<mxCell id="b" style="shape=mxgraph.gcp3.cloudrun;" vertex="1" parent="1"><mxGeometry x="80" y="0"'
        ' width="48" height="48" as="geometry"/></mxCell>'
        '<mxCell id="c" style="shape=image;image=data:image/svg+xml,PHN2Zy8+;" vertex="1" parent="1">'
        '<mxGeometry x="160" y="0" width="48" height="48" as="geometry"/></mxCell>'
        "</root></mxGraphModel></diagram></mxfile>"
    )


def test_lint_flags_unknown_vendor_shapes_in_foreign_files() -> None:
    bad = lint_text(foreign("shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.lambdaXYZ;"))
    hits = [f for f in bad if f.code == "LR-I001"]
    assert len(hits) == 1 and hits[0].severity == "warn" and hits[0].cell == "a"
    good = lint_text(foreign("shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.lambda;"))
    assert "LR-I001" not in codes(good)


# ---------------------------------------------------------------- export, CLI, doctor


def test_svg_export_embeds_library_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "a.drawio"
    src.write_text(build(aws()).xml)
    seen: list[list[str]] = []

    def fake_run(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        seen.append(args)
        Path(args[args.index("-o") + 1]).write_text("<svg/>")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(drawio_cli.subprocess, "run", fake_run)
    monkeypatch.setattr("ddraw.export.svg_post.add_accessibility", lambda *a: None)
    cli = drawio_cli.Cli(Path("/bin/drawio"), "32.7.4", [])
    drawio_cli.export(src, "svg", tmp_path / "a.svg", cli=cli)
    drawio_cli.export(src, "png", tmp_path / "a.png", cli=cli)
    assert "--embed-svg-images" in seen[0] and "--embed-svg-images" not in seen[1]
    assert seen[0][seen[0].index("--theme") + 1] == "light"


def test_icons_cli(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["icons", "search", "sqs", "queue", "--platform", "aws", "--json"]) == 0
    hits = json.loads(capsys.readouterr().out)
    assert hits[0]["id"] == "aws4:sqs" and hits[0]["family"] == "aws4"
    assert main(["icons", "show", "aws4:sqs", "--json"]) == 0
    assert "resIcon=mxgraph.aws4.sqs" in json.loads(capsys.readouterr().out)["style"]
    assert main(["icons", "show", "aws4:sqss"]) == 1
    assert "did you mean aws4:sqs" in capsys.readouterr().err
    assert main(["icons", "families", "--json"]) == 0
    assert {f["family"] for f in json.loads(capsys.readouterr().out)["families"]} >= {"aws4", "gcp"}
    assert main(["icons", "search"]) == 2


def test_doctor_warns_when_drawio_is_older_than_the_catalog() -> None:
    assert _icons_check("").status == "pass"
    assert _icons_check("1.0.0").status == "warn"
    assert _icons_check("999.0.0").status == "pass"


def test_unknown_icon_raises_on_build() -> None:
    data = aws()
    data["nodes"][3]["icon"] = "aws4:fargatex"
    with pytest.raises(DDError) as exc:
        build(data)
    assert exc.value.findings[0].code == "LR-I001"
