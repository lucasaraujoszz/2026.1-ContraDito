import Link from "next/link";

export default function NotFound() {
  return (
    <div className="pt-14 min-h-screen flex flex-col items-center justify-center gap-4 text-center px-4">
      <p className="font-data text-6xl font-bold text-dim">404</p>
      <h1 className="font-display text-2xl text-bright">Parlamentar não encontrado</h1>
      <p className="text-sm text-dim max-w-xs">
        Este parlamentar não está na nossa base de dados ou o endereço está incorreto.
      </p>
      <Link
        href="/"
        className="mt-2 px-5 py-2 text-sm text-mid border border-white/10 rounded-full hover:bg-card-alt hover:text-bright transition-colors"
      >
        Voltar ao Diretório
      </Link>
    </div>
  );
}
