🛟 Life Saver - Gestor Pessoal e Colaborativo
Dica para o GitHub: Adiciona aqui um screenshot ou um GIF curto a mostrar o Dashboard principal da tua aplicação.

Bem-vindo(a) ao Life Saver! Uma aplicação web full-stack desenvolvida para centralizar a gestão e organização pessoal. Mais do que uma simples To-Do list, o Life Saver integra gestão de tarefas, listas de compras, controlo de medicamentos, notas pessoais e um painel de métricas visuais.

O grande diferencial tecnológico deste projeto é o seu motor colaborativo: a arquitetura permite aos utilizadores estabelecerem ligações de amizade e partilharem recursos específicos (tarefas, listas), utilizando um sistema de controlo de permissões de edição em tempo real.

🚀 Arquitetura e Tecnologias
O projeto adota uma arquitetura MVC (Model-View-Controller) simplificada, separando claramente a lógica de negócio da interface, garantindo escalabilidade e facilidade de manutenção.

Backend (Lógica & API):

Python 3 & Flask: Desenvolvimento de rotas e construção de uma API RESTful.

Flask-Login: Gestão de sessões de utilizador com persistência segura.

Werkzeug Security: Hashing e verificação de palavras-passe (salting).

Base de Dados:

MySQL: Modelação de dados relacional (utilizadores, tarefas, listas, relacionamentos de amizade e partilha de permissões).

Frontend (Interface & Dinâmica):

HTML5, CSS3 & JavaScript (ES6): Interface responsive, construída de raiz com CSS Variables para gestão de um tema escuro dinâmico.

Fetch API: Comunicação assíncrona com o backend (AJAX), permitindo atualizações na interface sem necessidade de recarregar a página (ex: mudança de estado de tarefas, edição de perfil).

Chart.js: Renderização de gráficos interativos para visualização de dados e estatísticas.

✨ Funcionalidades Principais
Autenticação Segura: Registo, login e gestão de perfil de utilizadores.

Sistema de Amizades e RBAC (Role-Based Access Control): Envio e gestão de pedidos de amizade. Partilha granular de listas e tarefas com amigos, definindo permissões de "Apenas Leitura" ou "Edição".

Dashboard de Tarefas: Operações CRUD completas, com gestão de prazos e estados de conclusão.

Módulos Especializados: * Compras: Organização inteligente por categoria/supermercado.

Medicamentos: Registo de tomas, dosagens e horários.

Notas: Bloco de texto pessoal para acesso rápido.

Métricas Visuais: Painel analítico que calcula e exibe, através de gráficos, o rácio de produtividade e execução do utilizador.

🛠️ Como executar o projeto localmente
Pré-requisitos: * Python 3.x instalado.

Servidor MySQL a correr localmente (ex: XAMPP, MySQL Workbench, Docker).

1. Clonar o repositório

Bash
git clone https://github.com/o-teu-utilizador/life-saver.git
cd life-saver
2. Configurar o Ambiente Virtual (Recomendado)

Bash
python -m venv venv
# No Windows:
venv\Scripts\activate
# No macOS/Linux:
source venv/bin/activate
3. Instalar as dependências

Bash
pip install -r requirements.txt

4. Configurar a Base de Dados e Variáveis de Ambiente

Cria uma base de dados no teu servidor MySQL (ex: life_saver_db).

Importa o esquema da base de dados fornecido no ficheiro schema.sql (ou equivalente).

Renomeia o ficheiro .env.example para .env e preenche as tuas credenciais de acesso à base de dados e chaves secretas.

5. Iniciar o Servidor

Bash
flask run
# ou
python app.py
A aplicação estará disponível em http://localhost:5000.

📈 Próximos Passos (Roadmap)
Integração de notificações por E-mail/Push para tarefas prestes a expirar.

Recuperação de palavra-passe através de tokens temporários.

Otimização da acessibilidade (a11y) no Frontend.
