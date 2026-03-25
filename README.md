# 📋 Life Saver - Gestor Pessoal e Colaborativo

Bem-vindo(a) ao **Life Saver**! Uma aplicação web *full-stack* desenvolvida para centralizar a organização pessoal. Mais do que uma simples lista de tarefas (To-Do list), o Task Boss integra gestão de compras, controlo de medicamentos, notas pessoais e um sistema de estatísticas visuais.

O grande diferencial deste projeto é a sua **vertente colaborativa**: os utilizadores podem adicionar amigos e partilhar tarefas ou listas específicas, controlando permissões de edição em tempo real.

## Tecnologias Utilizadas

**Backend:**
* **Python 3 & Flask:** Lógica de rotas e API RESTful.
* **Flask-Login:** Gestão segura de sessões e autenticação.
* **MySQL:** Base de dados relacional para persistência de dados.
* **Werkzeug Security:** *Hashing* seguro de passwords.

**Frontend:**
* **HTML5, CSS3 & JavaScript (ES6):** Interface de utilizador responsiva e dinâmica (Fetch API para chamadas assíncronas).
* **Chart.js:** Renderização de gráficos interativos para a secção de estatísticas.
* **CSS Variables:** Implementação de um tema escuro consistente e moderno.

## Funcionalidades Principais

* **Autenticação Segura:** Registo e login de utilizadores com encriptação de passwords.
* **Dashboard de Tarefas:** Criação de tarefas (CRUD) com estados (pendente/concluído) e prazos.
* **Módulos Especializados:** * 🛒 *Listas de Compras* organizadas por supermercado/categoria.
  * *Gestão de Medicamentos* com registo de dosagens e horários.
  * *Bloco de Notas* pessoal para ideias rápidas.
* **Sistema de Amizades e Partilha:** Envio/aceitação de pedidos de amizade e partilha de itens específicos com permissões de leitura ou edição.
* **Dashboard Analítico:** Gráficos visuais que mostram o rácio de tarefas pendentes vs. concluídas.

## Como correr o projeto localmente

**Pré-requisitos:** Python 3.x e um servidor MySQL (ex: XAMPP, MySQL Workbench) a correr localmente.

1. **Clona o repositório:**
   ```bash
   git clone [https://github.com/beatrizvieitos/task-boss.git](https://github.com/beatrizvieitos/task-boss.git)
   cd task-boss
