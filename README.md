# Boot-Py: Bot de Backup Automatizado

Projeto de backup em Python com foco em confiabilidade, operacao continua e qualidade de entrega para uso real.

## Visao geral
O `Boot-Py` executa backup local de multiplos diretorios, valida integridade por checksum, gera relatorio JSON por execucao, aplica politica de retencao e pode enviar artefatos para S3 (ou endpoint compativel).

## Principais recursos
- Backup manual e agendado.
- Validacao de configuracao com mensagens claras.
- Retry para falhas de I/O.
- Compressao opcional em `.zip`.
- Dry-run para simulacao sem escrita.
- Exclusao por padroes (`exclude_patterns`).
- Retencao de backups e relatorios antigos.
- Logs em console e arquivo rotativo.
- Upload opcional para S3.
- Pipeline CI com testes automatizados.

## Estrutura do projeto
```text
.
|-- backup_bot.py
|-- config.json
|-- requirements.txt
|-- pyproject.toml
|-- CHANGELOG.md
|-- RELEASE.md
|-- CONTRIBUTING.md
|-- docs/
|   |-- EXEMPLOS_PRATICOS.md
|   `-- PADRAO_COMMITS_PT_BR.md
|-- tests/
|   `-- test_backup_bot.py
`-- .github/workflows/ci.yml
```

## Requisitos
- Python 3.9 ou superior
- Pip atualizado

## Instalacao
```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt
```

## Uso rapido
```bash
python backup_bot.py init-config
python backup_bot.py validate-config
python backup_bot.py run
```

## Comandos da CLI
```bash
python backup_bot.py --help

python backup_bot.py init-config
python backup_bot.py init-config --force

python backup_bot.py validate-config
python backup_bot.py show-config

python backup_bot.py run
python backup_bot.py run --dry-run
python backup_bot.py run --no-compress

python backup_bot.py schedule
python backup_bot.py schedule --run-now
```

## Configuracao (`config.json`)
```json
{
  "backup_dir": "./backups",
  "source_dirs": [
    "./documents",
    "./projects"
  ],
  "max_retries": 3,
  "retry_delay_seconds": 1.0,
  "compression": true,
  "schedule_time": "02:00",
  "retention_count": 7,
  "exclude_patterns": [
    "*.tmp",
    "*.log",
    "__pycache__/*"
  ],
  "log_file": "./backup.log",
  "log_level": "INFO",
  "hash_algorithm": "sha256",
  "s3": {
    "enabled": false,
    "bucket": "",
    "prefix": "backups",
    "region_name": "",
    "endpoint_url": "",
    "profile_name": "",
    "storage_class": "STANDARD",
    "acl": ""
  }
}
```

## Qualidade e testes
```bash
python -m unittest discover -s tests -v
```

CI: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

## Guias do projeto
- Guia de release: [`RELEASE.md`](RELEASE.md)
- Guia de contribuicao: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Padrao de commits PT_BR: [`docs/PADRAO_COMMITS_PT_BR.md`](docs/PADRAO_COMMITS_PT_BR.md)
- Exemplos praticos de uso: [`docs/EXEMPLOS_PRATICOS.md`](docs/EXEMPLOS_PRATICOS.md)
- Historico de versoes: [`CHANGELOG.md`](CHANGELOG.md)
- Licenca em portugues (referencia): [`LICENCA_PT_BR.md`](LICENCA_PT_BR.md)

## Execucao como servico
### Linux (`systemd`)
Arquivo `/etc/systemd/system/boot-py.service`:
```ini
[Unit]
Description=Boot-Py Backup Bot
After=network.target

[Service]
Type=simple
User=SEU_USUARIO
WorkingDirectory=/caminho/do/projeto
ExecStart=/caminho/python /caminho/do/projeto/backup_bot.py schedule --run-now
Restart=always

[Install]
WantedBy=multi-user.target
```

Comandos:
```bash
sudo systemctl daemon-reload
sudo systemctl enable boot-py
sudo systemctl start boot-py
```

### Windows (Agendador de Tarefas)
- Acao: iniciar `python.exe`
- Argumentos: `backup_bot.py run`
- Iniciar em: pasta raiz do projeto
- Gatilho: diario no horario desejado

## Publicacao no GitHub
Repositorio alvo: `https://github.com/Kaua-KGzin/Boot-Py`

Fluxo recomendado:
```bash
git clone https://github.com/Kaua-KGzin/Boot-Py.git
cd Boot-Py
git checkout -b feat/minha-melhoria
git add .
git commit -m "feat(readme): melhora fluxo recomendado para clonagem"
git push -u origin feat/minha-melhoria
```

Exemplo de commit em PT-BR:
```bash
git commit -m "fix(backup): corrige validacao de checksum na copia"
```

## Licenca
MIT. Texto legal oficial em [LICENSE](LICENSE) e referencia em PT-BR em [LICENCA_PT_BR.md](LICENCA_PT_BR.md).
