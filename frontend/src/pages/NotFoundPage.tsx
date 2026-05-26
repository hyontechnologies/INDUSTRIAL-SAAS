import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, AlertCircle } from 'lucide-react';

export default function NotFoundPage() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div className="w-20 h-20 bg-slate-100 text-slate-400 rounded-2xl flex items-center justify-center mb-6">
        <AlertCircle className="w-10 h-10" />
      </div>
      <h1 className="text-4xl font-bold text-slate-900 mb-2">404</h1>
      <h2 className="text-xl font-semibold text-slate-700 mb-4">Page not found</h2>
      <p className="text-slate-500 max-w-md mb-8">
        The page you are looking for might have been removed, had its name changed, or is temporarily unavailable.
      </p>
      <Link
        to="/dashboard"
        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg font-medium transition-colors shadow-sm"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Dashboard
      </Link>
    </div>
  );
}
