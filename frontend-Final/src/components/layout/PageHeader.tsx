import React from 'react';
import { LucideIcon } from 'lucide-react';

interface PageHeaderProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  actions?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({ title, description, icon: Icon, actions }) => {
  return (
    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
      <div className="flex items-center gap-3">
        {Icon && (
          <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
            <Icon className="w-5 h-5" />
          </div>
        )}
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{title}</h1>
          {description && <p className="text-sm text-slate-500 mt-1">{description}</p>}
        </div>
      </div>

      {actions && (
        <div className="flex items-center gap-3 shrink-0">
          {actions}
        </div>
      )}
    </div>
  );
};
