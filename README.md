# Migration Tool — Google Drive → Azure Blob Storage
### Aluno: Michell | Contêiner: `aluno-michell`

Interface web completa com backend Flask para migração e visualização de arquivos.

---

## Estrutura do projeto

```
migration-app/
├── api/
│   └── index.py          ← Backend Flask (API REST)
├── public/
│   └── index.html        ← Frontend (HTML/CSS/JS)
├── service_account.json  ← Credencial Google (você baixa)
├── requirements.txt      ← Dependências Python
├── start.py              ← Inicialização local (abre o navegador)
├── vercel.json           ← Configuração de deploy Vercel
└── README.md
```

---

## Rodar localmente

```bash
# 1. Instale as dependências
pip install -r requirements.txt

# 2. Coloque o service_account.json na raiz do projeto

# 3. Inicie o servidor (abre o navegador automaticamente)
python start.py
```

Acesse: **http://localhost:5000**

---

## Deploy no Vercel

### Pré-requisitos
- Conta em [vercel.com](https://vercel.com) (gratuita)
- [Vercel CLI](https://vercel.com/docs/cli) instalado: `npm i -g vercel`

### Passo a passo

```bash
# 1. Na pasta do projeto
cd migration-app

# 2. Login no Vercel
vercel login

# 3. Deploy
vercel

# 4. Para produção
vercel --prod
```

O Vercel detecta automaticamente o `vercel.json` e configura:
- `/api/*` → Python (Flask)
- `/*` → arquivos estáticos (HTML/CSS/JS)

### Variável de ambiente no Vercel (importante)

O `service_account.json` não deve subir para o Vercel. Em vez disso:

1. Copie todo o conteúdo do `service_account.json`
2. No painel do Vercel → Settings → Environment Variables
3. Crie: `GOOGLE_SERVICE_ACCOUNT_JSON` com o conteúdo JSON como valor
4. No `api/index.py`, a leitura do arquivo já suporta essa variável

---

## Funcionalidades da interface

| Função | Descrição |
|--------|-----------|
| Listar Drive | Lista todos os arquivos da pasta configurada |
| Listar Azure | Lista todos os blobs no contêiner `aluno-michell` |
| Migrar todos | Migra todos os arquivos do Drive para o Azure |
| Migrar unitário | Migra um único arquivo (botão ⬆ em cada linha) |
| URL pública | Exibe e copia a URL pública de cada blob |
| Console | Log em tempo real de cada transferência |
| Deletar blob | Remove um arquivo do Azure |
| Exportar log | Baixa o log de transferências em .txt |

---

## URL pública dos arquivos

Após a migração, cada arquivo estará acessível publicamente em:

```
https://stodsm6p2.blob.core.windows.net/aluno-michell/<nome-do-arquivo>
```

O contêiner foi criado com `PublicAccess.CONTAINER`, portanto o professor
pode acessar diretamente pela URL sem autenticação.
