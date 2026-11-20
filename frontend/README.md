# Frontend

Web interface for the AGF Co-Scientist API, written in React 19 and TypeScript with Vite, Tailwind CSS, Zustand for state and Recharts for charts.

## Run

Start the API first (see the [main README](../README.md)), then, in this directory:

```bash
npm install
npm run dev
```

Vite serves the interface at http://localhost:5173. It calls the API at `http://localhost:8000` unless `VITE_API_URL` is set.

`npm run build` type-checks and writes a production build to `dist/`; `npm run lint` runs ESLint; `npm run preview` serves the build.

## Pages

| Route | Page |
|---|---|
| `/` | Dashboard with Elo and quality charts for the active goal |
| `/chat` | Start a research session by submitting a goal, then ask questions about it |
| `/hypotheses` | Hypothesis list and a detail view for each hypothesis |
| `/settings` | Provider, models, API keys and run parameters |

## Caveats

- API keys entered on the settings page are kept in the browser's localStorage and sent to the API as request headers. The API applies them, and the chosen provider, only while it handles each request, so a run started here can end up using the keys and `LLM_PROVIDER` in the server's `.env`.
- The settings page offers Gemini and OpenAI only. Its per-agent model choices are sent with each goal, but the API does not apply them; set per-agent models and Bedrock on the server instead ([configuration](../docs/configuration.md)).
