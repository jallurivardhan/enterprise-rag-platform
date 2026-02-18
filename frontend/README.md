# Enterprise RAG Platform - Frontend

Next.js 14 frontend for the Enterprise RAG Platform with TypeScript, Tailwind CSS, and shadcn/ui.

## Features

- **Modern UI**: Built with Next.js 14 App Router, TypeScript, and Tailwind CSS
- **Component Library**: shadcn/ui for beautiful, accessible components
- **Chat Interface**: Real-time chat with streaming support
- **Document Upload**: Drag-and-drop file upload with progress tracking
- **Source Attribution**: Clickable source references with metadata
- **Responsive Design**: Mobile-friendly layout

## Getting Started

See [SETUP.md](./SETUP.md) for detailed setup instructions.

## Quick Start

1. Install dependencies:
```bash
npm install
```

2. Set up environment variables:
```bash
cp .env.local.example .env.local
# Edit .env.local with your API URL
```

3. Run development server:
```bash
npm run dev
```

## Project Structure

- `src/app/` - Next.js App Router pages and layouts
- `src/components/` - React components organized by feature
- `src/lib/` - Utilities and API client
- `src/types/` - TypeScript type definitions
- `src/hooks/` - Custom React hooks

## Design System

- **Primary**: Slate-900
- **Accent**: Blue-600
- **Background**: White / Slate-50
- **Font**: Inter (from Google Fonts)

## API Integration

The frontend communicates with the FastAPI backend via the API client in `src/lib/api.ts`. Make sure the backend is running on the URL specified in `NEXT_PUBLIC_API_URL`.
