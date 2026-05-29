# Frontend (Vite + React + TypeScript)

The frontend is a Vite + React application styled with Tailwind CSS and shadcn/ui components.

## Project Structure

```text
front-end/
├── src/
│   ├── components/     # Shared UI
│   │   └── ui/         # shadcn/ui components
│   ├── features/       # Feature API/types/state
│   ├── hooks/          # Shared hooks
│   ├── lib/            # Client utilities
│   ├── assets/         # Bundled assets
│   ├── routes.tsx      # App routes
│   └── App.tsx         # App shell
├── public/             # Static assets
└── package.json        # Scripts and dependencies
```

## Adding components

To add components to your app, run the following command:

```bash
npx shadcn@latest add button
```

This will place the ui components in the `src/components/ui` directory.

## Using components

To use the components in your app, import them as follows:

```tsx
import { Button } from "@/components/ui/button"
```

## Environment Variables

The frontend uses Vite environment variables. Only `VITE_*` keys are exposed to the browser.

- `VITE_API_URL`: Browser-facing API base URL (runtime).
- `VITE_PROXY_TARGET`: Optional dev server proxy target override.
