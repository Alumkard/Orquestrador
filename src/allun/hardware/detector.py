"""Coleta de informações de hardware."""

from __future__ import annotations

import shutil
import subprocess

import psutil

from .modelos import GPU, PerfilHardware

_GB = 1024**3


def _vram_nvidia_smi() -> list[float]:
    """VRAM (GB) de cada GPU NVIDIA via nvidia-smi; lista vazia se indisponível."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    try:
        saida = subprocess.run(
            [exe, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
        return [float(linha) / 1024 for linha in saida.splitlines() if linha.strip()]
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def _detectar_gpus(avisos: list[str]) -> list[GPU]:
    try:
        from gpu_detector import detect

        brutas = detect()
    except Exception as erro:  # noqa: BLE001  biblioteca externa de precisão variável
        avisos.append(f"Falha ao detectar GPU ({erro}); seguindo sem GPU.")
        return []

    gpus: list[GPU] = []
    for g in brutas:
        mb = getattr(g, "memory_mb", None)
        gpus.append(
            GPU(
                nome=g.name,
                fabricante=getattr(g, "vendor", None),
                vram_gb=round(mb / 1024, 2) if mb else None,
            )
        )

    # No Windows o WMI limita a VRAM a 4 GB; corrige placas NVIDIA com nvidia-smi.
    nvidia_idx = [i for i, g in enumerate(gpus) if (g.fabricante or "").lower() == "nvidia"]
    reais = _vram_nvidia_smi()
    if nvidia_idx and len(reais) == len(nvidia_idx):
        for i, vram in zip(nvidia_idx, reais):
            gpus[i] = GPU(gpus[i].nome, gpus[i].fabricante, round(vram, 2))
    elif any(g.vram_gb is None and g.fabricante and g.fabricante.lower() != "apple" for g in gpus):
        avisos.append("VRAM de alguma GPU não foi informada pelo sistema; ela foi ignorada.")

    return gpus


def detectar_hardware() -> PerfilHardware:
    avisos: list[str] = []
    memoria = psutil.virtual_memory()
    nucleos = psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 1
    return PerfilHardware(
        ram_total_gb=round(memoria.total / _GB, 2),
        ram_disponivel_gb=round(memoria.available / _GB, 2),
        nucleos=nucleos,
        gpus=_detectar_gpus(avisos),
        avisos=avisos,
    )
