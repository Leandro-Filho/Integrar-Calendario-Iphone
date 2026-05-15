# Projeto de Integração com o Calendário do iPhone usando CalDAV

Este projeto faz uma integração entre o **Calendário do iPhone/iCloud** e um **backend em Python**, usando o protocolo **CalDAV**.

Na prática, ele permite que o sistema busque eventos do calendário, leia informações como:

- nome do evento;
- data;
- horário;
- notas/descrição;
- calendário de origem;

e depois possa salvar esses dados em um banco de dados.

Ou seja:

```text
Calendário do iPhone → Backend Python → Banco de Dados
```

Um pequeno túnel secreto entre sua agenda e seu sistema.

## Primeiro Passo: Criar o ambiente virtual e instalar as dependências

Antes de tudo, crie um ambiente virtual .venv na raiz do projeto:

```bash
python -m venv .venv
```
Depois ative o ambiente virtual.

```bash
No Linux/macOS:

.venv\Scripts\activate

No Windows:

.venv\Scripts\activate
```
Com o ambiente virtual ativado, instale as dependências:

```bash
pip install fastapi uvicorn caldav icalendar python-dotenv pandas sqlalchemy psycopg2-binary
```
Esse comando instala as bibliotecas necessárias para o projeto rodar com sucesso.


## Segundo Passo: Preparar o ambiente do iCloud

Essa parte é fundamental. Sem isso, o backend vai bater na porta do iCloud e tomar um belo “não autorizado”. 🚪

Crie um arquivo .env na raiz do projeto, seguindo o modelo do arquivo .env.example.

Exemplo:

```bash
APPLE_ID=seu_email_do_icloud_ou_apple_id
APPLE_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
CALDAV_URL=https://caldav.icloud.com/
DATABASE_URL=sua_url_do_banco_de_dados
```

## Terceiro Passo: Criar a senha específica de app da Apple

Agora vem a chave do castelo. 🏰

Acesse https://account.apple.com/ e faça login com o e-mail cadastrado na sua Conta Apple. Depois vá em Sign-In and Security → App-Specific Passwords Crie uma nova senha específica de app. A Apple vai gerar uma senha no formato parecido com xxxx-xxxx-xxxx-xxxx Essa é a senha que deve ir no .env. 

Atenção: não use sua senha normal da Apple.

A senha normal é a chave da casa inteira. A senha específica de app é só a chave da portinha do calendário.

## Quarto Passo: Configurar o calendário padrão no iPhone

Este projeto está configurado para buscar apenas eventos do calendário chamado "Trabalho". Então, para facilitar sua vida e não precisar marcar manualmente todo evento como “Trabalho”, você pode deixar esse calendário como padrão no iPhone.

No iPhone, vá em Ajustes → Apps → Calendário → Calendário Padrão e depois iCloud → Trabalho. A partir disso, todo evento novo criado no app Calendário será salvo automaticamente no calendário Trabalho.

Assim, o backend consegue encontrar os eventos sem drama, sem caça ao tesouro e sem gremlin escondido.

## Quinto Passo: Rodar o projeto

Com tudo configurado, rode:
```bash
uvicorn main:app --reload
```

Se tudo estiver certo, você verá algo parecido com: Uvicorn running on http://127.0.0.1:8000. Agora a mágica está oficialmente ligada. 