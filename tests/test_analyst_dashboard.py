"""Dashboard fictício: conteúdo, escape, escrita explícita e ausência de rede."""

from __future__ import annotations

import html
import json
import os
import socket
import subprocess
import sys
import webbrowser
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from footballiq import analyst_demo as demo
from footballiq.analyst_dashboard import render_dashboard, save_dashboard
from footballiq.analyst_interpretation import Fact, InterpretationResult
from footballiq.analytics import analyze_recent_matches


class Document(HTMLParser):
    """Recolhe estrutura e atributos reais, sem confundir texto escapado com tags."""

    def __init__(self, source: str) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []
        self.feed(source)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Guarda atributos para verificar IDs, links locais e recursos externos."""
        self.elements.append((tag, dict(attrs)))


@pytest.fixture(autouse=True)
def no_connections() -> Iterator[None]:
    """Mesmo loopback é proibido: todos os estados LLM são simulados nos testes."""
    with (
        patch.object(socket.socket, "connect", side_effect=AssertionError("Sem rede")),
        patch.object(
            socket, "create_connection", side_effect=AssertionError("Sem rede")
        ),
    ):
        yield


def test_complete_dashboard_uses_factual_values_without_mutation() -> None:
    report = demo.load_demo_report()
    before = report.model_dump_json()
    document = render_dashboard(report)
    assert report.model_dump_json() == before
    assert "DADOS FICTÍCIOS" in document
    assert "Analisa os últimos cinco jogos da minha equipa." in document
    assert document.count("<strong>2</strong>") == 2
    assert document.count("<strong>1</strong>") == 1
    assert document.count("<strong>4</strong>") == 2
    assert "Cobertura 5/5" in document
    assert "Golos a favor" in document and "Golos contra" in document
    assert "not_requested" in document
    assert document.index('id="match-0"') < document.index('id="match-1"')
    assert 'datetime="2026-11-08T15:00:00Z"' in document
    assert "Equipa Ficticia B" in document
    assert "synthetic-five-v1" in document
    for mid in (10, 9, 8, 7, 6):
        assert f"synthetic-match-{mid}-v1" in document
        assert f"internal_match:{mid}" in document


@pytest.mark.parametrize(
    "scenario, coverage", [("partial_match", "0/1"), ("empty", "0/0")]
)
def test_null_is_never_displayed_as_zero(scenario: str, coverage: str) -> None:
    document = demo.render_demo_dashboard(scenario)
    assert document.count("<strong>—</strong>") == 5
    assert "<strong>0</strong>" not in document
    assert f"Cobertura {coverage}" in document
    assert "Total da janela indisponível" in document
    if scenario == "empty":
        assert "Ainda sem jogos neste snapshot" in document
        assert "Sem referências de jogos" in document
    else:
        assert "shots: unknown." in document
        assert "Resultado unverified." in document
        assert "Indisponível</span>" in document


def test_partial_coverage_labels_subtotals_without_filling_total() -> None:
    payload = json.loads(
        (Path(__file__).parent / "fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )
    payload["matches"][0]["score"]["status"] = "unverified"
    document = render_dashboard(analyze_recent_matches(payload))
    assert "Cobertura 4/5" in document
    assert "Subtotal dos jogos cobertos — não é o total da janela." in document
    assert document.count("<strong>—</strong>") == 5
    assert "Resultado unverified." in document


def test_malicious_dto_text_is_escaped_not_markup() -> None:
    report = demo.load_demo_report()
    hostile = '<script>alert("x")</script><img src="https://invalid.test/x" onerror="x"> & \' '
    report.matches[0].opponent_name = hostile
    report.matches[0].reference.data_version = hostile
    report.matches[0].score_provenance.reference_ids = [hostile]
    report.warnings = [hostile]
    report.snapshot_version = hostile
    document = render_dashboard(report)
    assert hostile not in document
    assert html.escape(hostile, quote=True) in document
    parsed = Document(document)
    assert not any(
        tag in {"script", "img", "iframe", "object", "embed"}
        for tag, _ in parsed.elements
    )
    assert not any(
        key.startswith("on") for _, attrs in parsed.elements for key in attrs
    )


def test_untrusted_interpretation_cannot_inject_text_or_references() -> None:
    report = demo.load_demo_report()
    result = InterpretationResult(
        "available",
        "<script>unsafe()</script>",
        (Fact("match:10", '<img src="https://invalid.test">', ("match:999",)),),
    )
    document = render_dashboard(report, result)
    assert "unavailable" in document
    assert "Interpretação não verificável" in document
    assert "unsafe()" not in document and "match:999" not in document


def test_unavailable_warning_is_escaped() -> None:
    result = InterpretationResult(
        "unavailable", warning='<iframe src="https://invalid.test"></iframe>'
    )
    document = render_dashboard(demo.load_demo_report(), result)
    assert "&lt;iframe" in document
    assert not any(tag == "iframe" for tag, _ in Document(document).elements)


def test_available_state_uses_validated_facts_with_local_links() -> None:
    client = MagicMock()
    client.chat.return_value = json.dumps(
        {
            "summary": "selection",
            "observations": [{"fact_id": "match:10", "references": ["match:10"]}],
        }
    )
    document = demo.render_demo_dashboard(with_llm=True, client=client)
    assert '<span class="state">available</span>' in document
    assert "Jogo 10: 2–1" in document
    assert '<a href="#match-0">match:10</a>' in document
    client.chat.assert_called_once()


def test_fallback_leaves_all_factual_content_visible() -> None:
    client = MagicMock()
    client.chat.side_effect = TimeoutError()
    document = demo.render_demo_dashboard(with_llm=True, client=client)
    assert '<span class="state">unavailable</span>' in document
    assert "tempo de espera" in document
    assert document.count("<strong>4</strong>") == 2
    assert "synthetic-five-v1" in document


def test_default_html_never_calls_llm() -> None:
    client = MagicMock()
    assert "not_requested" in demo.render_demo_dashboard(client=client)
    client.chat.assert_not_called()


def test_empty_opt_in_does_not_call_llm() -> None:
    client = MagicMock()
    document = demo.render_demo_dashboard("empty", with_llm=True, client=client)
    assert "unavailable" in document
    assert "Sem jogos" in document
    client.chat.assert_not_called()


def test_accessible_responsive_self_contained_structure() -> None:
    source = demo.render_demo_dashboard()
    parsed = Document(source)
    assert ("html", {"lang": "pt-PT"}) in parsed.elements
    ids = {attrs["id"] for _, attrs in parsed.elements if "id" in attrs}
    for tag, attrs in parsed.elements:
        if "href" in attrs:
            assert tag == "a" and attrs["href"].startswith("#")
            assert attrs["href"][1:] in ids
        assert "src" not in attrs and "srcset" not in attrs
    assert "@media(max-width:540px)" in source
    assert "@media(max-width:900px)" in source
    assert ":focus-visible" in source
    assert "prefers-reduced-motion" in source
    assert "V Vitória · E Empate · D Derrota" in source
    assert "Saltar para o conteúdo" in source
    assert "script-src 'none'" in source
    assert "connect-src 'none'" in source
    assert "url(" not in source and "@import" not in source
    assert not any(
        tag in {"script", "link", "form", "iframe", "img"} for tag, _ in parsed.elements
    )


@pytest.mark.parametrize("scenario", ["complete_five", "partial_match", "empty"])
def test_stable_generation_matches_engine(scenario: str) -> None:
    report = demo.load_demo_report(scenario)
    assert demo.render_demo_dashboard(scenario) == render_dashboard(report)
    assert demo.render_demo_dashboard(scenario) == demo.render_demo_dashboard(scenario)


def test_write_requires_explicit_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "demo.html"
    document = demo.render_demo_dashboard()
    assert save_dashboard(document, path) == path
    with pytest.raises(FileExistsError):
        save_dashboard("replacement", path)
    assert path.read_text(encoding="utf-8") == document
    save_dashboard("replacement", path, overwrite=True)
    assert path.read_text(encoding="utf-8") == "replacement"


def test_temporary_destination_is_outside_checkout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    path = save_dashboard(demo.render_demo_dashboard())
    assert path.parent == tmp_path and path.suffix == ".html"
    assert path.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_other_extensions_and_missing_parents_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        save_dashboard("HTML", tmp_path / "README.md", overwrite=True)
    with pytest.raises(FileNotFoundError):
        save_dashboard("HTML", tmp_path / "missing/demo.html")


def test_symlink_is_rejected_even_when_overwrite_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(Path, "is_symlink", lambda _: True)
    with pytest.raises(ValueError):
        save_dashboard("HTML", tmp_path / "demo.html", overwrite=True)


def test_cli_html_writes_only_requested_destination_without_opening(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    opened = MagicMock()
    monkeypatch.setattr(webbrowser, "open", opened)
    path = tmp_path / "demo.html"
    assert demo.main(["--html", "--output", str(path)]) == 0
    assert "Dashboard criado:" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == demo.render_demo_dashboard()
    opened.assert_not_called()
    assert demo.main(["--html", "--output", str(path)]) == 1
    assert "--overwrite" in capsys.readouterr().err


def test_cli_opens_only_with_explicit_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened = MagicMock(return_value=True)
    monkeypatch.setattr(webbrowser, "open", opened)
    path = tmp_path / "demo.html"
    assert demo.main(["--html", "--output", str(path), "--open"]) == 0
    opened.assert_called_once_with(path.as_uri())


@pytest.mark.parametrize(
    "arguments", [["--output", "demo.html"], ["--open"], ["--overwrite"]]
)
def test_html_only_arguments_do_not_change_terminal_cli(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as result:
        demo.main(arguments)
    assert result.value.code == 2


def test_non_demo_identity_is_rejected() -> None:
    report = demo.load_demo_report()
    report.source_instance_id = "operational"
    with pytest.raises(ValueError):
        render_dashboard(report)


def test_browser_failure_does_not_lose_generated_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    opened = MagicMock(side_effect=OSError("browser unavailable"))
    monkeypatch.setattr(webbrowser, "open", opened)
    path = tmp_path / "demo.html"
    assert demo.main(["--html", "--output", str(path), "--open"]) == 0
    assert path.is_file()
    assert "Abra manualmente" in capsys.readouterr().err


def test_html_entry_point_needs_no_database_or_network(tmp_path: Path) -> None:
    """O HTML funciona num processo limpo mesmo bloqueando a infraestrutura SQL."""
    script = """
import importlib.abc, runpy, socket, sys
from unittest.mock import patch
class NoDatabase(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"sqlalchemy", "psycopg", "httpx", "ollama"} or fullname.startswith("footballiq.db"):
            raise AssertionError("No database required for HTML")
def forbidden(*args, **kwargs):
    raise AssertionError("No network in HTML generation")
sys.meta_path.insert(0, NoDatabase())
sys.argv = ["footballiq.analyst_demo", "--html", "--output", sys.argv[1]]
with patch.object(socket.socket, "connect", forbidden), patch.object(socket, "create_connection", forbidden):
    runpy.run_module("footballiq.analyst_demo", run_name="__main__")
"""
    path = tmp_path / "isolated.html"
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(path)],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert path.read_text(encoding="utf-8") == demo.render_demo_dashboard()


def test_skip_target_and_result_names_have_accessible_semantics() -> None:
    """O atalho transfere foco programático e os símbolos têm nomes independentes da cor."""
    parsed = Document(demo.render_demo_dashboard())
    mains = [attrs for tag, attrs in parsed.elements if tag == "main"]
    assert len(mains) == 1
    assert mains[0]["id"] == "content" and mains[0]["tabindex"] == "-1"
    results = [
        attrs
        for tag, attrs in parsed.elements
        if tag == "span" and "result " in attrs.get("class", "")
    ]
    assert [attrs["aria-label"] for attrs in results[:5]] == [
        "Vitória",
        "Vitória",
        "Empate",
        "Derrota",
        "Empate",
    ]
    assert all(attrs["role"] == "img" and attrs["aria-label"] for attrs in results)
    assert any(attrs.get("class") == "brand-name" for _, attrs in parsed.elements)


def test_rendered_accessibility_regressions_when_browser_available(
    tmp_path: Path,
) -> None:
    """Regressão visual opt-in: texto longo, zoom, foco, contraste e impressão reais.

    Não instala ferramentas. O módulo Playwright já instalado é fornecido por
    variável de ambiente; a suite normal continua independente do navegador.
    """
    module = os.environ.get("FOOTBALLIQ_PLAYWRIGHT_MODULE")
    if not module:
        pytest.skip(
            "Browser QA opcional exige FOOTBALLIQ_PLAYWRIGHT_MODULE já instalado"
        )
    for scenario in ("complete_five", "partial_match", "empty"):
        save_dashboard(
            demo.render_demo_dashboard(scenario), tmp_path / f"{scenario}.html"
        )
    report = demo.load_demo_report()
    report.matches[0].opponent_name = "CLUBE_FICTICIO_" * 35
    report.snapshot_version = "SNAPSHOT_FICTICIO_" * 35
    report.matches[0].reference.data_version = "VERSAO_FICTICIA_" * 35
    report.warnings.append("AVISO_FICTICIO_" * 35)
    save_dashboard(render_dashboard(report), tmp_path / "long-content.html")
    script = r"""
const {chromium}=require(process.env.FOOTBALLIQ_PLAYWRIGHT_MODULE);
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-background-networking']});
 try{
  for(const viewport of [{width:1440,height:900},{width:390,height:844}]){
   const context=await browser.newContext({viewport});let external=0;
   await context.route('**/*',route=>{if(/^https?:/.test(route.request().url())){external++;return route.abort();}return route.continue();});
   const page=await context.newPage();
   for(const scenario of ['complete_five','partial_match','empty','long-content']){
    await page.goto(pathToFileURL(path.join(process.env.FOOTBALLIQ_BROWSER_FIXTURES,scenario+'.html')).href);
    assert.equal(await page.locator('h1').count(),1);
    assert.equal(await page.locator('main').count(),1);
    assert.equal(await page.locator('.badge').textContent(),'DADOS FICTÍCIOS');
    assert.equal(await page.locator('script').count(),0);
    if(scenario==='complete_five')assert.deepEqual(await page.locator('.sequence .result').allTextContents(),['V','V','E','D','E']);
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement.className),'skip');
    await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(()=>document.activeElement.id),'content');
    for(const zoom of ['1','2']){
     await page.evaluate(value=>document.documentElement.style.zoom=value,zoom);
     assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,scenario+' horizontal overflow at '+zoom);
     assert.equal(await page.locator('.brand-name').evaluate(e=>getComputedStyle(e).whiteSpace),'nowrap');
     assert.equal(await page.locator('.brand').evaluate(e=>e.scrollWidth<=e.clientWidth),true,'Brand must remain legible at zoom');
    }
    await page.evaluate(()=>document.documentElement.style.zoom='1');
    if(await page.locator('details').count()){
     await page.locator('summary').first().focus();
     assert.notEqual(await page.locator('summary').first().evaluate(e=>getComputedStyle(e).outlineStyle),'none');
     await page.keyboard.press('Enter');
     assert.equal(await page.locator('details').first().evaluate(e=>e.open),true);
     await page.keyboard.press('Enter');
     assert.equal(await page.locator('details').first().evaluate(e=>e.open),false);
     await page.emulateMedia({media:'print'});
     assert.equal(await page.locator('details dd').first().evaluate(e=>e.checkVisibility()),true);
     assert.equal(await page.locator('.sidebar').evaluate(e=>getComputedStyle(e).display),'none');
     await page.emulateMedia({media:'screen'});
    }
    const ratios=await page.evaluate(()=>{
     function lum(c){return (c.match(/[\d.]+/g)||[]).slice(0,3).map(Number).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);}
     return ['.muted','.badge','.win','.draw','.loss','.unknown','.notice','.eyebrow','.sidebar nav a'].flatMap(selector=>{
      const e=document.querySelector(selector);if(!e||!e.checkVisibility())return [];
      let parent=e,bg;while(parent){bg=getComputedStyle(parent).backgroundColor;if(bg!=='rgba(0, 0, 0, 0)')break;parent=parent.parentElement;}
      const values=[lum(getComputedStyle(e).color),lum(bg)].sort((a,b)=>a-b);
      return [(values[1]+.05)/(values[0]+.05)];
     });
    });
    assert.ok(ratios.every(value=>value>=4.5),'Text contrast');
    assert.equal(external,0);
   }
   await context.close();
  }
 }finally{await browser.close();}
 console.log('Browser regressions: desktop/mobile, long text, zoom 200%, keyboard, print and contrast passed');
})().catch(error=>{console.error(error.message);process.exitCode=1;});
"""
    result = subprocess.run(
        ["node"],
        input=script,
        env={**os.environ, "FOOTBALLIQ_BROWSER_FIXTURES": str(tmp_path)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Browser regressions:" in result.stdout
