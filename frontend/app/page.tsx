import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Background Orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-500/20 rounded-full blur-[120px] pointer-events-none animate-pulse-slow"></div>
      <div className="absolute bottom-1/4 right-1/4 w-[30rem] h-[30rem] bg-indigo-500/10 rounded-full blur-[120px] pointer-events-none"></div>

      <div className="glass-card max-w-2xl w-full mx-4 p-12 text-center animate-fade-in z-10 border-white/10 relative overflow-hidden">
        {/* Decorative inner glow */}
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-brand-500/50 to-transparent"></div>

        <div className="mb-10">
          <div className="inline-flex items-center justify-center p-4 bg-brand-500/10 rounded-2xl mb-8 border border-brand-500/20 shadow-lg shadow-brand-500/10">
            <svg
              className="w-12 h-12 text-brand-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"
              />
            </svg>
          </div>
          <h1 className="text-6xl font-bold text-white mb-4 tracking-tight">
            VM<span className="text-brand-400">Ledger</span>
          </h1>
          <p className="text-xl text-gray-400 max-w-lg mx-auto leading-relaxed">
            Premium infrastructure intelligence. Monitor, manage, and scale your
            instances with unparalleled clarity.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
          <Link
            href="/login"
            className="w-full sm:w-auto px-8 py-4 bg-brand-500 hover:bg-brand-400 text-white rounded-xl hover:scale-[1.02] transition-all duration-300 font-bold shadow-[0_0_20px_rgba(45,212,191,0.3)] hover:shadow-[0_0_30px_rgba(45,212,191,0.5)] flex items-center justify-center"
          >
            Sign In
            <svg
              className="w-5 h-5 ml-2"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M14 5l7 7m0 0l-7 7m7-7H3"
              />
            </svg>
          </Link>
          <Link
            href="/register"
            className="w-full sm:w-auto px-8 py-4 bg-surface-800 hover:bg-surface-700 text-white rounded-xl hover:scale-[1.02] transition-all duration-300 font-bold border border-white/10 hover:border-white/20 shadow-xl flex items-center justify-center"
          >
            Create Account
          </Link>
        </div>

        <div className="mt-12 pt-8 border-t border-white/5 flex items-center justify-center gap-8 text-sm font-medium text-gray-500 uppercase tracking-widest">
          <span className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse"></span>
            Real-time Metrics
          </span>
          <span className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse delay-75"></span>
            Secure Access
          </span>
        </div>
      </div>
    </div>
  );
}
