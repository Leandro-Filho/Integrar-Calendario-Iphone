# Projeto de Integração Utilizando CalDAV Para Integrar o Calendário do Iphone!!!!

## Primeiro Passo - Instalar as dependências!

Você deve criar um .venv e depois, rode o seguinte código:

```bash
pip install fastapi uvicorn caldav icalendar python-dotenv pandas
```

Esse pip install vai instalar TODAS as dependências para o projeto rodar com sucesso!

## Segundo Passo - Preparar o Ambiente do Icloud Para a Integração

Essa parte é fundamental para que a integração e a conversação do backend e seu calendário seja feita sem erro!

Crie um .env na raiz do projeto, seguindo como exemplo o arquivo **.env.example** para que seja possível usar as credencias.

Depois, acesse **https://account.apple.com/**, insira seu email cadastrado no seu Icloud do seu celular, sua senha do Icloud para conseguir criar sua senha de app.

Após conseguir entrar, procure **App-Specific Passwords**, depois crie seu "Token" e pegue a senha que tem esse seguinte formato xxxx-xxxx-xxxx. Com isso, você já tem a senha para conseguir conectar com seu calendário.

## Terceiro Passo - Alterar o Status das Criações de Eventos Dentro do Calendário

Esse código apenas serve para retirar os eventos linkados como "Trabalho", ou seja, para inibir o trabalho de marcar o evento como trabalho, vou te mostrar como deixar isso automático.

Você deve ir em "Ajustes" -> "Apps" -> "Calendário" -> "Calendário Padrão" -> Deixe marcado como "Trabalho".

Assim, você já pode só adicionar um evento e textar.

## Quarto Passo - Rodar o main.py e Mágica!!!!

O código já é responsável por criar um endpoint para puxar os eventos e guardar no banco de dados, então você terá que apenas rodar o seguinte código: 

```bash
uvicorn main:app --reload
```

Assim, ele fará a MÁGICA de tirar os eventos do seu Calendário. 