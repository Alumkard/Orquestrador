import pytest

from allun.catalogo import carregar_catalogo
from allun.hardware import GPU, Perfil, PerfilHardware, classificar
from allun.recomendador import Preferencia, recomendar


def hw(ram=16, nucleos=8, gpus=None, livre=None):
    return PerfilHardware(ram, livre if livre is not None else ram * 0.6, nucleos, gpus or [])


@pytest.mark.parametrize(
    "maquina, esperado",
    [
        (hw(ram=4, nucleos=2), Perfil.LEVE),
        (hw(ram=7, nucleos=8), Perfil.LEVE),
        (hw(ram=8, nucleos=4), Perfil.MEDIO),
        (hw(ram=16, nucleos=8), Perfil.MEDIO),
        (hw(ram=32, nucleos=8), Perfil.POTENTE),
        (hw(ram=16, nucleos=2), Perfil.LEVE),  # poucos núcleos rebaixam
        (hw(ram=8, nucleos=8, gpus=[GPU("RTX 4070", "NVIDIA", 12)]), Perfil.POTENTE),
        (hw(ram=8, nucleos=8, gpus=[GPU("UHD", "Intel", None)]), Perfil.MEDIO),
        (hw(ram=16, nucleos=8, gpus=[GPU("M2", "Apple", None)]), Perfil.MEDIO),
        (hw(ram=32, nucleos=8, gpus=[GPU("M2", "Apple", None)]), Perfil.POTENTE),
    ],
)
def test_classificar(maquina, esperado):
    assert classificar(maquina) == esperado


def test_gpu_sem_vram_e_ignorada():
    assert hw(gpus=[GPU("X", "AMD", None)]).memoria_modelo_gb == 8.0


def test_igpu_com_2gb_nao_e_dedicada():
    # caso real: Iris Xe reporta 2 GB no WMI e não pode rebaixar uma máquina de 20 GB
    m = hw(ram=19.7, gpus=[GPU("Intel(R) Iris(R) Xe Graphics", "Intel", 2.0)])
    assert not m.gpu_dedicada and classificar(m) == Perfil.MEDIO


def test_gpu_pequena_nao_reduz_capacidade_da_ram():
    assert hw(ram=32, gpus=[GPU("GTX 1650", "NVIDIA", 4)]).memoria_modelo_gb == 16.0


def test_maquina_antiga_recebe_modelo_leve():
    r = recomendar(hw(ram=4, nucleos=2), carregar_catalogo())
    assert r.principal.id in {"gemma3:1b", "llama3.2:1b"}
    assert r.online_gratuitos and r.online_pagos


def test_maquina_potente_recebe_modelo_grande():
    r = recomendar(hw(ram=8, gpus=[GPU("RTX", "NVIDIA", 24)]), carregar_catalogo())
    assert r.principal.id == "qwen2.5:14b"


def test_nenhum_local_cabe_cai_para_online_gratuito():
    r = recomendar(hw(ram=2, nucleos=2), carregar_catalogo())
    assert r.principal.tipo == "online" and r.principal.custo == "gratuito"
    assert r.avisos


def test_somente_local_sem_modelo_retorna_none():
    r = recomendar(hw(ram=2), carregar_catalogo(), Preferencia.SOMENTE_LOCAL)
    assert r.principal is None and not r.online_gratuitos


def test_somente_online_exclui_locais():
    r = recomendar(hw(), carregar_catalogo(), Preferencia.SOMENTE_ONLINE)
    assert r.principal.tipo == "online" and not r.alternativas_locais


def test_margem_de_seguranca():
    # 6 GB de RAM -> 3 GB úteis; llama3.2:3b exige 3.0 * 1.1 = 3.3, não cabe
    r = recomendar(hw(ram=6, nucleos=8), carregar_catalogo())
    assert r.principal.id == "llama3.2:1b"


def test_modelos_de_especialidade_nao_sao_o_padrao_geral():
    r = recomendar(hw(ram=8, gpus=[GPU("RTX", "NVIDIA", 24)]), carregar_catalogo())
    ids = [m.id for m in [r.principal, *r.alternativas_locais]]
    assert not any("coder" in i for i in ids)
