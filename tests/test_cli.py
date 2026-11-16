from allun.catalogo import carregar_catalogo
from allun.cli import formatar_diagnostico, main
from allun.hardware import GPU, PerfilHardware
from allun.recomendador import recomendar


def test_formatar_diagnostico():
    hw = PerfilHardware(16, 8, 8, [GPU("RTX 4070", "NVIDIA", 12)])
    texto = formatar_diagnostico(hw, recomendar(hw, carregar_catalogo()))
    assert "Perfil: potente" in texto
    assert "dedicada" in texto and "Principal:" in texto


def test_main_diagnostico(capsys):
    assert main(["diagnostico", "--preferencia", "somente_online"]) == 0
    saida = capsys.readouterr().out
    assert "== Hardware ==" in saida and "Principal:" in saida
