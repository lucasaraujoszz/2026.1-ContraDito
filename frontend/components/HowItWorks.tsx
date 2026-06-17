export function HowItWorks() {
  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 pb-14">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="glass rounded-xl p-6 space-y-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-pulse">01</p>
          <h3 className="font-display text-lg font-bold text-bright leading-snug">
            Discurso<br />
            <span className="italic font-normal text-mid">encontra</span> voto
          </h3>
          <p className="text-sm text-mid leading-relaxed">
            A IA compara o que cada parlamentar declarou em plenário com o voto
            que registrou nas mesmas proposições — cruzando texto e dado oficial.
          </p>
        </div>
        <div className="glass rounded-xl p-6 space-y-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-coherent">02</p>
          <h3 className="font-display text-lg font-bold text-bright leading-snug">
            Score de<br />
            <span className="italic font-normal text-mid">Coerência</span>
          </h3>
          <p className="text-sm text-mid leading-relaxed">
            Calculado sobre os votos válidos — ausências e abstenções ficam de
            fora. Cada votação analisada conta: votos alinhados ao discurso
            sobem o score, contradições o reduzem.
          </p>
        </div>
        <div className="glass rounded-xl p-6 space-y-3">
          <p className="text-[10px] uppercase tracking-[0.2em] text-aurum">03</p>
          <h3 className="font-display text-lg font-bold text-bright leading-snug">
            Transparência,<br />
            <span className="italic font-normal text-mid">não veredicto</span>
          </h3>
          <p className="text-sm text-mid leading-relaxed">
            O ContraDito organiza informação pública num só lugar. O julgamento
            é seu — a plataforma apenas torna o contraste visível.
          </p>
        </div>
      </div>
    </section>
  );
}
