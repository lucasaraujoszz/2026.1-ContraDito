export function Hero() {
  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 pt-14 pb-10 text-center">
      <div className="inline-flex flex-col items-center gap-2 mb-8">
        <p className="text-[10px] uppercase tracking-[0.35em] text-dim">
          Câmara · Senado · Brasil
        </p>
        <div className="font-display font-black text-[3.5rem] sm:text-[5rem] md:text-[7rem] leading-none tracking-tight">
          <span className="text-bright">CONTRA</span><span className="text-coherent italic font-normal">dito</span>
        </div>
        <div className="flex items-center gap-3 mt-1">
          <div className="h-px w-12 bg-gradient-to-r from-transparent to-rim" />
          <p className="text-[10px] uppercase tracking-[0.3em] text-dim">
            transparência parlamentar via IA
          </p>
          <div className="h-px w-12 bg-gradient-to-l from-transparent to-rim" />
        </div>
      </div>
      <h1 className="font-display font-bold text-bright leading-[1.05] text-4xl sm:text-5xl md:text-[4.5rem]">
        O que foi{" "}
        <span className="italic font-normal text-mid">dito</span>{" "}
        <span className="text-coherent">vs.</span>{" "}
        realidade
      </h1>
    </section>
  );
}
