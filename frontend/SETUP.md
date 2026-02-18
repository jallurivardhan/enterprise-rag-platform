# Frontend Setup Guide

## Prerequisites

1. Node.js 18+ installed
2. npm or yarn package manager

## Initial Setup

1. **Initialize Next.js project** (run in project root):
```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir
```

When prompted:
- Use TypeScript? **Yes**
- Use ESLint? **Yes**
- Use Tailwind CSS? **Yes**
- Use `src/` directory? **Yes**
- Use App Router? **Yes**
- Customize the default import alias? **No** (or use default)

2. **Install shadcn/ui**:
```bash
cd frontend
npx shadcn@latest init
```

When prompted:
- Which style would you like to use? **Default**
- Which color would you like to use as base color? **Slate**
- Where is your global CSS file? **src/app/globals.css**
- Would you like to use CSS variables for colors? **Yes**
- Where is your tailwind.config.js located? **tailwind.config.ts** (or default)
- Configure the import alias for components? **@/components**
- Configure the import alias for utils? **@/lib/utils**

3. **Add shadcn/ui components**:
```bash
npx shadcn@latest add button
npx shadcn@latest add input
npx shadcn@latest add card
npx shadcn@latest add scroll-area
npx shadcn@latest add avatar
npx shadcn@latest add badge
npx shadcn@latest add toast
npx shadcn@latest add dialog
npx shadcn@latest add dropdown-menu
npx shadcn@latest add separator
npx shadcn@latest add skeleton
npx shadcn@latest add textarea
```

4. **Install additional dependencies**:
```bash
npm install clsx class-variance-authority tailwind-merge lucide-react
```

5. **Create environment file**:
```bash
cp .env.local.example .env.local
```

Edit `.env.local` and set:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Development

Run the development server:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
frontend/
├── src/
│   ├── app/              # Next.js App Router
│   ├── components/       # React components
│   │   ├── chat/        # Chat-related components
│   │   ├── upload/      # Upload components
│   │   ├── layout/      # Layout components
│   │   └── ui/          # shadcn/ui components
│   ├── lib/             # Utilities and API client
│   ├── types/           # TypeScript type definitions
│   └── hooks/           # Custom React hooks
└── public/              # Static assets
```

## Notes

- The UI components in `src/components/ui/` are placeholder implementations. After running `shadcn add`, they will be replaced with the official shadcn/ui components.
- Some components may need adjustments after shadcn/ui installation.
- The toast hook is a simplified implementation - you may want to use the full shadcn/ui toast component after installation.
