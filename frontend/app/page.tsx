export default function Home() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 to-gray-800">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-white mb-4">
          VMLedger
        </h1>
        <p className="text-xl text-gray-300 mb-8">
          Lightweight CMDB and Monitoring Tool
        </p>
        <div className="space-x-4">
          <a
            href="/login"
            className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Login
          </a>
          <a
            href="/register"
            className="inline-block px-6 py-3 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors"
          >
            Register
          </a>
        </div>
      </div>
    </div>
  );
}
