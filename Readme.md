# Installation and Setup Guide

This project is containerized using Docker, allowing you to run both the backend and frontend with a single command.

## Prerequisites

- [Docker](https://www.docker.com/get-started) installed on your machine.
- [Docker Compose](https://docs.docker.com/compose/install/) (usually included with Docker Desktop).

## Quick Start

1.  **Clone the repository** :
    ```bash
    git clone https://github.com/shoxyouness/ai-agent.git
    cd ai-agent
    ```

2.  **Environment Setup**:
    - Ensure you have a `.env` file in the `backend` directory.
    - If not, copy the example or create one based on `backend/.env` (if available) or `backend/config.py`.

3.  **Run the Application**:
    Run the following command in the root directory of the project:
    ```bash
    docker-compose up --build
    ```

    This command will:
    - Build the Docker images for both backend and frontend.
    - Start the services.

4.  **Access the App**:
    - **Frontend**: Open [http://localhost:3000](http://localhost:3000) in your browser.
    - **Backend API**: Open [http://localhost:8000/docs](http://localhost:8000/docs) to view the API documentation.

## Stopping the Application

To stop the application, press `Ctrl+C` in the terminal where it's running, or run:

```bash
docker-compose down
```

## Troubleshooting

-   **Port Conflicts**: If ports 3000 or 8000 are already in use, modify the `ports` section in `docker-compose.yml`.
-   **Rebuilding**: If you make changes to the code, you may need to rebuild the images:
    ```bash
    docker-compose up --build
    ```
