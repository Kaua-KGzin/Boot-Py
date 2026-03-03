# Exemplos Praticos (PT_BR)

Este guia traz cenarios reais para operar o Boot-Py com seguranca e previsibilidade.

## 1. Backup local diario (sem S3)

### Configuracao sugerida
```json
{
  "backup_dir": "./backups",
  "source_dirs": ["./documents", "./projects"],
  "max_retries": 3,
  "retry_delay_seconds": 1.5,
  "compression": true,
  "schedule_time": "02:30",
  "retention_count": 10,
  "exclude_patterns": ["*.tmp", "*.log", "__pycache__/*"],
  "log_file": "./backup.log",
  "log_level": "INFO",
  "hash_algorithm": "sha256",
  "s3": { "enabled": false }
}
```

### Execucao
```bash
python backup_bot.py validate-config
python backup_bot.py run
python backup_bot.py schedule --run-now
```

## 2. Simulacao antes de entrar em producao
Use `dry-run` para validar escopo e exclusoes sem gravar nada.

```bash
python backup_bot.py run --dry-run
```

## 3. Backup para S3

### Configuracao minima S3
```json
{
  "s3": {
    "enabled": true,
    "bucket": "meu-bucket-de-backup",
    "prefix": "boot-py/producao",
    "region_name": "us-east-1",
    "storage_class": "STANDARD"
  }
}
```

### Credenciais
Escolha uma estrategia:
- Variaveis de ambiente (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- Profile local (`~/.aws/credentials`)
- IAM Role (EC2/ECS/Lambda)

## 4. Operacao com mais seguranca
- Mantenha `compression=true` para reduzir custo de armazenamento.
- Use `retention_count` compativel com sua politica de auditoria.
- Salve `backup.log` em local monitorado.
- Rode os testes no pipeline antes de release.

## 5. Diagnostico rapido
- Validar config:
  - `python backup_bot.py validate-config`
- Ver detalhes de configuracao efetiva:
  - `python backup_bot.py show-config`
- Aumentar verbosidade temporaria:
  - `python backup_bot.py --log-level DEBUG run`
