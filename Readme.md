# AIPËR - AI Personal Agent

AIPËR is a comprehensive AI-powered personal assistant designed to streamline your daily tasks. Built with a robust Python backend (FastAPI, LangGraph) and a modern Next.js frontend, this agent orchestrates multiple specialized sub-agents to handle emails, calendar management, contact retrieval, and web research.

## Features

- **Supervisor Agent**: Orchestrates tasks and routes requests to specialized agents based on user intent.
- **Email Agent**: Manages your inbox, reads and summarizes emails, and drafts replies using Microsoft Graph.
- **Calendar Agent**: Checks availability, schedules meetings, and manages your calendar via Microsoft Graph.
- **Sheet Agent**: Manages contacts and user preferences using Google Sheets as a database.
- **Deep Research Agent**: Performs reliable web research for facts, news, and comparisons.
- **Browser Agent**: Handles browser automation tasks when interaction (clicking, filling forms) is required.
- **Memory & Context**: Maintains long-term memory to personalize interactions and adhere to user preferences.

---

## Installation

### Prerequisites

For the installation and operation of the application, the following components are required:

- **Git**: For cloning and managing the source code.
- **Docker Desktop**: For container-based execution (including Docker Compose).
- **Python 3.11 or higher**: For the backend (only for manual installation).
- **Node.js 18 or higher** and **npm**: For the frontend (only for manual installation).
- **API Keys**: Valid credentials for OpenAI, Google (optional), Microsoft Graph, and Clerk (authentication).

To support a reproducible installation, the repository additionally contains a `.env.example` file. This file documents all environment variables necessary for the operation of the application in a structured form, without containing sensitive information such as API keys or client secrets.

The file serves as a template for creating the respective `.env` files in the backend, frontend, and root directories. Users can copy the `.env.example` file and supplement the required values according to their local environment. This ensures that all necessary configuration parameters are transparently documented and configuration errors during installation are minimized.

### Installation with Docker (Recommended)

The container-based installation represents the recommended variant, as it ensures a consistent runtime environment for the backend and frontend and reduces the installation effort.

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/shoxyouness/ai-agent.git
    cd ai-agent
    ```

2.  **Configuration of Environment Variables:**
    - Create a `.env` file in the `backend` directory based on the `.env.example` template. This file includes, among other things, the Microsoft Graph configuration (see Section [Microsoft Graph Configuration](#microsoft-graph-configuration)).
    - Create a `.env` file in the root directory of the project for the Frontend and Docker setup, specifically:
        ```env
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=your_clerk_public_key
        CLERK_SECRET_KEY=your_clerk_secret_key
        ```

3.  **Initialization of Microsoft Graph:**
    To use the email and calendar functions, initial authentication tokens must be generated. Execute the setup script locally in the `backend` directory (see Section [Initial Token Generation](#initial-token-generation)).
    Since this directory is mounted as a volume into the container, the generated tokens will subsequently be available within the Docker environment.

4.  **Start the Application:**
    ```bash
    docker-compose up --build
    ```
    This command creates the Docker images for the backend and frontend and starts all necessary services.

5.  **Access the Application:**
    - **Frontend:** [http://localhost:3000](http://localhost:3000)
    - **Backend API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)

### Manual Installation

Alternatively, the backend and frontend can be installed and started independently of each other. This variant is particularly suitable for development or debugging purposes.

#### Backend Installation

1.  Switch to the backend directory:
    ```bash
    cd backend
    ```

2.  Install the Python dependencies (using a virtual environment is recommended):
    ```bash
    pip install .
    ```

3.  Install the browsers required for web automation:
    ```bash
    playwright install --with-deps chromium
    ```

4.  Create a `.env` file in the `backend` directory and configure the required environment variables based on the `.env.example` file.

5.  Start the Backend Server:
    ```bash
    python src/api/run_api.py
    ```
    The server is subsequently reachable at [http://localhost:8000](http://localhost:8000).

#### Frontend Installation

1.  Switch to the frontend directory:
    ```bash
    cd frontend
    ```

2.  Install the Node.js dependencies:
    ```bash
    npm install
    ```

3.  Create a `.env` file in the `frontend` directory:
    ```env
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=your_key
    CLERK_SECRET_KEY=your_key
    BACKEND_URL=http://localhost:8000
    ```

4.  Start the development server:
    ```bash
    npm run dev
    ```
    The frontend is subsequently reachable at [http://localhost:3000](http://localhost:3000).

### Microsoft Graph Configuration

For email and calendar functionality, the agent uses the Microsoft Graph API. This requires a one-time setup of an Azure application and the generation of access tokens.

#### Azure App Registration

1.  Log in to the [Microsoft Azure Portal](https://portal.azure.com).
2.  Create a new app registration under "App registrations".
3.  Select "Accounts in any organizational directory and personal Microsoft accounts".
4.  Configure the Redirect URI (Web) to `http://localhost`.
5.  Note the `Application (client) ID`.
6.  Create a `Client Secret` and save the secret value.

For the scope of functions implemented in this work, only the following delegated Microsoft Graph permissions are required:

- `User.Read` – Enables user login and reading basic profile data.
- `Mail.Read` – Enables reading incoming emails for analysis and summarization.
- `Mail.Send` – Enables sending emails on behalf of the user.
- `Calendars.ReadWrite` – Enables reading, creating, changing, and deleting calendar entries.

The configuration takes place in the file `backend/.env`:
```env
APPLICATION_ID=your_application_id
CLIENT_SECRET=your_client_secret
REDIRECT_URI=http://localhost
```

#### Initial Token Generation

Since the agent works in the background without direct user interaction, the initial authentication process must be performed manually once:

```bash
python src/utils/ms_graph.py
```

The script guides you through the authentication process and saves the access data in the file `src/utils/ms_graph_tokens.json` after successful login. This file is used by the agent for automatic renewal of access tokens and is mounted into the container via a volume when using Docker.
