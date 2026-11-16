# Design: Núcleo do Allun

## Fluxo
```
detectar_hardware() -> PerfilHardware -> classificar() -> Perfil
                                                |
carregar_catalogo() -> [ModeloLLM] ------> recomendar(perfil, catalogo, preferencia) -> Recomendacao
```

## Componentes
- `hardware/modelos.py`: `GPU`, `PerfilHardware` (ram_total_gb, ram_disponivel_gb, nucleos, gpus, avisos, propriedades `gpu_dedicada`, `apple_silicon`, `memoria_modelo_gb`) e enum `Perfil`.
- `hardware/detector.py`: `detectar_hardware()` usa `psutil` e `gpu_detector.detect()`. Importação e chamada de `gpu_detector` ficam dentro de `try/except`. Para NVIDIA, tenta `nvidia-smi` para corrigir VRAM subestimada (limite de 4 GB do WMI).
- `hardware/perfil.py`: `classificar(PerfilHardware) -> Perfil`, função pura.
- `catalogo/gerenciador.py`: `carregar_catalogo(caminho=None) -> list[ModeloLLM]`, validando campos.
- `recomendador/motor.py`: `recomendar(hw, catalogo, preferencia) -> Recomendacao` com `principal`, `alternativas_locais`, `online_gratuitos`, `online_pagos`, `avisos`.

## Decisões
- A memória útil, e não a RAM bruta, define o perfil. Uma máquina de 8 GB com RTX de 12 GB é `potente` apesar da RAM.
- GPU integrada não conta como VRAM (o WMI reporta, por exemplo, 2 GB para uma Iris Xe, que usa memória compartilhada). A memória útil é o maior valor entre VRAM e metade da RAM, então uma GPU pequena não piora a máquina.
- Margem de 10% evita recomendar um modelo no limite exato.
- Modelos locais seguem o formato `ollama` com a tag exata; online usam o nome do `litellm`.

## Testes
Funções puras com `PerfilHardware` simulado: máquina antiga, notebook comum, GPU dedicada, Apple Silicon, falha de GPU, preferências.

