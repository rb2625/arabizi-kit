from arabizikit.cli import main


def test_cli_basic(capsys):
    assert main(["ana 3ayz 2akol"]) == 0
    out = capsys.readouterr().out
    assert "أنا عايز آكل" in out


def test_cli_top_k(capsys):
    assert main(["saa3a", "--top-k", "3"]) == 0
    out = capsys.readouterr().out
    assert "ساعة" in out
    assert "[2]" in out or "[3]" in out


def test_cli_dialect(capsys):
    assert main(["shlonak ya 5al", "--dialect"]) == 0
    out = capsys.readouterr().out
    assert "gulf" in out


def test_cli_eval(capsys):
    assert main(["--eval"]) == 0
    out = capsys.readouterr().out
    assert "arabizikit benchmark" in out
    assert "gulf" in out


def test_cli_normalize(capsys):
    assert main(["--normalize", "أنا", "شكراً"]) == 0
    out = capsys.readouterr().out
    assert "انا" in out
    assert "شكرا" in out


def test_cli_no_args_prints_help(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "usage" in out.lower()
