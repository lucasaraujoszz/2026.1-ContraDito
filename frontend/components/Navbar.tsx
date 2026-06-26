import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";

export function Navbar() {
  return (
    <nav className="fixed top-0 inset-x-0 z-50 h-14 border-b border-rim/20 bg-canvas/90 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto h-full px-4 sm:px-6 flex items-center justify-between">
        <Link href="/" className="text-base font-bold tracking-tight">
          <span className="text-bright">CONTRA</span>
          <span className="text-coherent">DITO</span>
        </Link>

        <div className="flex items-center gap-1">
          <ThemeToggle />
          <Link
            href="/comparacao"
            className="px-4 py-1.5 text-sm text-mid hover:text-bright border border-white/10 rounded-full transition-colors hover:border-white/20"
          >
            Comparação
          </Link>
          <Link
            href="/"
            className="px-4 py-1.5 text-sm text-mid hover:text-bright transition-colors"
          >
            Diretório
          </Link>
        </div>
      </div>
    </nav>
  );
}
