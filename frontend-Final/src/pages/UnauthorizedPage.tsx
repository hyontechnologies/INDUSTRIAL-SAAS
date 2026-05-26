import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert, ArrowLeft } from 'lucide-react';

export default function UnauthorizedPage() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[calc(100vh-4rem)]">
      <div className="w-16 h-16 bg-rose-100 rounded-full flex items-center justify-center mb-6">
        <ShieldAlert className="w-8 h-8 text-rose-600" />
      </div>
      <h1 className="text-3xl font-bold text-slate-900 mb-2">Access Denied</h1>
      <p className="text-slate-500 mb-8 max-w-md text-center">
        You do not have permission to access this page. Please contact your system administrator if you believe this is an error.
      </p>
      <Link
        to="/"
        className="flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors"
      >
        <ArrowLeft className="w-5 h-5" />
        Return to Dashboard
      </Link>
    </div>
  );
}
